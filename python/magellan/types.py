#
# Copyright 2015 Ram Sriharsha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import json
import sys

from itertools import izip

from pyspark import SparkContext
from pyspark.sql.types import DataType, UserDefinedType, StructField, StructType, \
    ArrayType, DoubleType, IntegerType

__all__ = ['Point']


class Shape(DataType):

    __initialized__ = False

    def registerPicklers(self):
        if Point.__initialized__ == False:
            sc = SparkContext._active_spark_context
            loader = sc._jvm.Thread.currentThread().getContextClassLoader()
            wclass = loader.loadClass("org.apache.spark.sql.magellan.EvaluatePython")
            wmethod = None
            for mthd in wclass.getMethods():
                if mthd.getName() == "registerPicklers":
                    wmethod = mthd

            expr_class = sc._jvm.java.lang.Object
            java_args = sc._gateway.new_array(expr_class, 0)
            wmethod.invoke(None, java_args)
            Point.__initialized__ = True


class PointUDT(UserDefinedType):
    """User-defined type (UDT).

    .. note:: WARN: SpatialSDK Internal Use Only
    """

    @classmethod
    def sqlType(cls):
        return Point()

    @classmethod
    def module(cls):
        """
        The Python module of the UDT.
        """
        return "magellan.types"

    @classmethod
    def scalaUDT(cls):
        """
        The class name of the paired Scala UDT.
        """
        return "magellan.PointUDT"

    def serialize(self, obj):
        """
        Converts the a user-type object into a SQL datum.
        """
        if isinstance(obj, Point):
            return obj
        else:
            raise TypeError("cannot serialize %r of type %r" % (obj, type(obj)))

    def deserialize(self, datum):
        """
        Converts a SQL datum into a user-type object.
        """
        if isinstance(datum, Point):
            return datum
        else:
            assert len(datum) == 3, \
                "PointUDT.deserialize given row with length %d but requires 3" % len(datum)
            tpe = datum[0]
            assert tpe == 1, "Point should have type = 1"
            return Point(datum[1], datum[2])

    def simpleString(self):
        return 'point'

    @classmethod
    def fromJson(cls, json):
        return Point(json['x'], json['y'])


class Point(Shape):
    """
    A point is a zero dimensional shape.
    The coordinates of a point can be in linear units such as feet or meters,
    or they can be in angular units such as degrees or radians.
    The associated spatial reference specifies the units of the coordinates.
    In the case of a geographic coordinate system, the x-coordinate is the longitude
    and the y-coordinate is the latitude.

    >>> v = Point(1.0, 2.0)
    Point([1.0, 2.0])
    """

    __UDT__ = PointUDT()

    def __init__(self, x = 0.0, y = 0.0):
        self._shape_type = 1
        self.x = x
        self.y = y

    def __str__(self):
        return "Point (" + str(self.x) + "," + str(self.y) + ")"

    def __repr__(self):
        return self.__str__()

    def __unicode__(self):
        return self.__str__()

    def __reduce__(self):
        return (Point, (self.x, self.y))

    def __eq__(self, other):
        return isinstance(other, Point) and self.x == other.x and self.y == other.y

    @classmethod
    def fromJson(cls, json):
        return Point(json['x'], json['y'])

    def jsonValue(self):
        self.registerPicklers()
        return {"type": "udt",
                "pyClass": "magellan.types.PointUDT",
                "class": "magellan.PointUDT",
                "sqlType": "magellan.Point"}


class PolygonUDT(UserDefinedType):
    """User-defined type (UDT).

    .. note:: WARN: SpatialSDK Internal Use Only
    """
    pointUDT = PointUDT()

    @classmethod
    def sqlType(cls):
        """
        Underlying SQL storage type for this UDT.
        """
        return Polygon()

    @classmethod
    def module(cls):
        """
        The Python module of the UDT.
        """
        return "magellan.types"

    @classmethod
    def scalaUDT(cls):
        """
        The class name of the paired Scala UDT.
        """
        return "magellan.PolygonUDT"

    def serialize(self, obj):
        """
        Converts the a user-type object into a SQL datum.
        """
        if isinstance(obj, Polygon):
            return obj
        else:
            raise TypeError("cannot serialize %r of type %r" % (obj, type(obj)))

    def deserialize(self, datum):
        """
        Converts a SQL datum into a user-type object.
        """
        if isinstance(datum, Polygon):
            return datum
        else:
            assert len(datum) == 3, \
                "PolygonUDT.deserialize given row with length %d but requires 4" % len(datum)
            tpe = datum[0]
            assert tpe == 5, "Polygon should have type = 5"
            return Polygon(datum[1], [self.pointUDT.deserialize(point) for point in datum[2]])

    def simpleString(self):
        return 'polygon'

    @classmethod
    def fromJson(cls, json):
        indices = json["indices"]
        points = [PointUDT.fromJson(point) for point in json["points"]]
        return Polygon(indices, points)


class Polygon(Shape):
    """
    A polygon consists of one or more rings. A ring is a connected sequence of four or more points
    that form a closed, non-self-intersecting loop. A polygon may contain multiple outer rings.
    The order of vertices or orientation for a ring indicates which side of the ring is the interior
    of the polygon. The neighborhood to the right of an observer walking along the ring
    in vertex order is the neighborhood inside the polygon.
    Vertices of rings defining holes in polygons are in a counterclockwise direction.
    Vertices for a single, ringed polygon are, therefore, always in clockwise order.
    The rings of a polygon are referred to as its parts.
    >>> v = Polygon([0], [Point(1.0, 1.0), Point(1.0, -1.0), Point(1.0, 1.0))
    Point([-1.0,-1.0, 1.0, 1.0], [0], Point(1.0, 1.0), Point(1.0, -1.0), Point(1.0, 1.0))
    """

    __UDT__ = PolygonUDT()

    def __init__(self, indices = [], points = []):
        self._shape_type = 5
        self.indices = indices
        self.points = points

    def __str__(self):
        inds = "[" + ",".join([str(i) for i in self.indices]) + "]"
        pts = "[" + ",".join([str(v) for v in self.points]) + "]"
        return "Polygon (" + ",".join((inds, pts)) + ")"

    def __repr__(self):
        return self.__str__()

    def __reduce__(self):
        return (Polygon, (self.indices, self.points))

    @classmethod
    def fromJson(cls, json):
        indices = json["indices"]
        points = [PointUDT.fromJson(point) for point in json["points"]]
        return Polygon(indices, points)

    def jsonValue(self):
        self.registerPicklers()
        return {"type": "udt",
                "pyClass": "magellan.types.PolygonUDT",
                "class": "magellan.Polygon",
                "sqlType": "magellan.Polygon"}


class PolyLineUDT(UserDefinedType):
    """User-defined type (UDT).

    .. note:: WARN: SpatialSDK Internal Use Only
    """

    pointUDT = PointUDT()

    @classmethod
    def sqlType(cls):
        """
        Underlying SQL storage type for this UDT.
        """
        return PolyLine()

    @classmethod
    def module(cls):
        """
        The Python module of the UDT.
        """
        return "magellan.types"

    @classmethod
    def scalaUDT(cls):
        """
        The class name of the paired Scala UDT.
        """
        return "magellan.PolyLineUDT"

    def serialize(self, obj):
        """
        Converts the a user-type object into a SQL datum.
        """
        if isinstance(obj, PolyLine):
            return obj
        else:
            raise TypeError("cannot serialize %r of type %r" % (obj, type(obj)))

    def deserialize(self, datum):
        """
        Converts a SQL datum into a user-type object.
        """
        if isinstance(datum, PolyLine):
            return datum
        else:
            assert len(datum) == 3, \
                "PolyLineUDT.deserialize given row with length %d but requires 4" % len(datum)
            print datum
            tpe = datum[0]
            assert tpe == 3, "PolyLine should have type = 3"
            return PolyLine(datum[1], [self.pointUDT.deserialize(point) for point in datum[2]])

    def simpleString(self):
        return 'polyline'

    @classmethod
    def fromJson(cls, json):
        indices = json["indices"]
        points = [PointUDT.fromJson(point) for point in json["points"]]
        return PolyLine(indices, points)


class PolyLine(Shape):
    """
    A PolyLine is an ordered set of vertices that consists of one or more parts.
    A part is a connected sequence of two or more points.
    Parts may or may not be connected to one another.
    Parts may or may not intersect one another
    >>> v = PolyLine([0], [Point(1.0, 1.0), Point(1.0, -1.0), Point(1.0, 0.0))
    Point([0], Point(1.0, 1.0), Point(1.0, -1.0), Point(1.0, 0.0))
    """

    __UDT__ = PolyLineUDT()

    def __init__(self, indices = [], points = []):
        self._shape_type = 3
        self.indices = indices
        self.points = points

    def __str__(self):
        inds = "[" + ",".join([str(i) for i in self.indices]) + "]"
        pts = "[" + ",".join([str(v) for v in self.points]) + "]"
        return "Polygon (" + ",".join((inds, pts)) + ")"

    def __repr__(self):
        return self.__str__()

    def __reduce__(self):
        return (PolyLine, (self.indices, self.points))

    @classmethod
    def fromJson(cls, json):
        indices = json["indices"]
        points = [PointUDT.fromJson(point) for point in json["points"]]
        return PolyLine(indices, points)

    def jsonValue(self):
        self.registerPicklers()
        return {"type": "udt",
                "pyClass": "magellan.types.PolyLineUDT",
                "class": "magellan.PolyLine",
                "sqlType": "magellan.PolyLine"}


def _inbound_shape_converter(json_string):
    j = json.loads(json_string)
    shapeType = str(j["pyClass"])  # convert unicode to str
    split = shapeType.rfind(".")
    module = shapeType[:split]
    shapeClass = shapeType[split+1:]
    m = __import__(module, globals(), locals(), [shapeClass])
    UDT = getattr(m, shapeClass)
    return UDT.fromJson(j)

# This is used to unpickle a Row from JVM
def _create_row_inbound_converter(dataType):
    return lambda *a: dataType.fromInternal(a)

