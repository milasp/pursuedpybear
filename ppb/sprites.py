from inspect import getfile
from pathlib import Path
from typing import Union

import ppb
from ppb import Vector
from ppb.events import EventMixin
from ppb.utils import FauxFloat

import ppb_vector


TOP = "top"
BOTTOM = "bottom"
LEFT = "left"
RIGHT = "right"

error_message = "'{klass}' object does not have attribute '{attribute}'"
side_attribute_error_message = error_message.format


class Side(FauxFloat):
    """
    Acts like a float, but also has a variety of accessors.
    """
    sides = {
        LEFT: ('x', -1),
        RIGHT: ('x', 1),
        TOP: ('y', 1),
        BOTTOM: ('y', -1)
    }

    def __init__(self, parent: 'BaseSprite', side: str):
        self.side = side
        self.parent = parent

    def __repr__(self):
        return f"Side({self.parent!r}, {self.side!r})"

    def __str__(self):
        return str(float(self))

    def _lookup_side(self, side):
        dimension, sign = self.sides[side]
        return dimension, sign * self.parent._offset_value

    def __float__(self):
        dimension, offset = self._lookup_side(self.side)
        return self.parent.position[dimension] + offset

    @property
    def top(self) -> Vector:
        """
        Get the corner vector
        """
        self._attribute_gate(TOP, [TOP, BOTTOM])
        return Vector(float(self), float(self.parent.top))

    @top.setter
    def top(self, value):
        self._attribute_gate(TOP, [TOP, BOTTOM])
        self.parent.position = self._mk_update_vector_side(TOP, value)

    @property
    def bottom(self) -> Vector:
        """
        Get the corner vector
        """
        self._attribute_gate(BOTTOM, [TOP, BOTTOM])
        return Vector(float(self), float(self.parent.bottom))

    @bottom.setter
    def bottom(self, value):
        self._attribute_gate(BOTTOM, [TOP, BOTTOM])
        self.parent.position = self._mk_update_vector_side(BOTTOM, value)

    @property
    def left(self) -> Vector:
        """
        Get the corner vector
        """
        self._attribute_gate(LEFT, [LEFT, RIGHT])
        return Vector(float(self.parent.left), float(self))

    @left.setter
    def left(self, value):
        self._attribute_gate(LEFT, [LEFT, RIGHT])
        self.parent.position = self._mk_update_vector_side(LEFT, value)

    @property
    def right(self) -> Vector:
        """
        Get the corner vector
        """
        self._attribute_gate(RIGHT, [LEFT, RIGHT])
        return Vector(float(self.parent.right), float(self))

    @right.setter
    def right(self, value):
        self._attribute_gate(RIGHT, [LEFT, RIGHT])
        self.parent.position = self._mk_update_vector_side(RIGHT, value)

    @property
    def center(self) -> Vector:
        """
        Get the midpoint vector
        """
        if self.side in (TOP, BOTTOM):
            return Vector(self.parent.center.x, float(self))
        else:
            return Vector(float(self), self.parent.center.y)

    @center.setter
    def center(self, value):
        self.parent.position = self._mk_update_vector_center(value)

    def _mk_update_vector_side(self, attribute, value: Vector):
        """
        Calculate the updated vector, based on the given corner.

        That is, handles the calculation for forms like sprite.top.left = vector
        """
        value = Vector(value)
        assert attribute != 'center'
        # Does a bunch of dynamc resolution:
        # Sprite.top.left
        #        ^   ^ attribute
        #        self.side
        self_dimension, self_offset = self._lookup_side(self.side)

        attr_dimension, attr_offset = self._lookup_side(attribute)

        assert self_dimension != attr_dimension

        fields = {
            self_dimension: value[self_dimension] - self_offset,
            attr_dimension: value[attr_dimension] - attr_offset,
        }
        return Vector(fields)

    def _mk_update_vector_center(self, value):
        """
        Calculate the update vector, based on the given side.

        That is, handles the calculation for forms like sprite.right = number
        """
        value = Vector(value)
        # Pretty similar to ._mk_update_vector_side()
        self_dimension, self_offset = self._lookup_side(self.side)

        attr_dimension = 'y' if self_dimension == 'x' else 'x'

        fields = {
            self_dimension: value[self_dimension] - self_offset,
            attr_dimension: value[attr_dimension]
        }

        return Vector(fields)

    def _attribute_gate(self, attribute, bad_sides):
        if self.side in bad_sides:
            name = type(self).__name__
            message = side_attribute_error_message(klass=name,
                                                   attribute=attribute)
            raise AttributeError(message)


class Rotatable:
    """
    A simple rotation mixin. Can be included with sprites.
    """
    _rotation = 0
    # This is necessary to make facing do the thing while also being adjustable.
    #: The baseline vector, representing the "front" of the sprite
    basis = Vector(0, -1)
    # Considered making basis private, the only reason to do so is to
    # discourage people from relying on it as data.

    @property
    def facing(self):
        """
        The direction the "front" is facing
        """
        return Vector(*self.basis).rotate(self.rotation).normalize()

    @facing.setter
    def facing(self, value):
        self.rotation = self.basis.angle(value)

    @property
    def rotation(self):
        """
        The amount the sprite is rotated, in degrees
        """
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        self._rotation = value % 360

    def rotate(self, degrees):
        """
        Rotate the sprite by a given angle (in degrees).
        """
        self.rotation += degrees


class BaseSprite(EventMixin, Rotatable):
    """
    The base Sprite class. All sprites should inherit from this (directly or
    indirectly).
    """
    #: (:py:class:`ppb.Image`): The image asset
    image = None
    #: (:py:class:`ppb.Vector`): Location of the sprite
    position: Vector = Vector(0, 0)
    #: The width/height of the sprite (sprites are square)
    size: Union[int, float] = 1

    def __init__(self, **kwargs):
        super().__init__()

        self.position = Vector(self.position)

        # Initialize things
        for k, v in kwargs.items():
            # Abbreviations
            if k == 'pos':
                k = 'position'
            # Castings
            if k == 'position':
                v = Vector(v)
            setattr(self, k, v)

        # Trigger some calculations
        self.size = self.size

    @property
    def center(self) -> Vector:
        """
        The position of the center of the sprite
        """
        return self.position

    @center.setter
    def center(self, value: ppb_vector.VectorLike):
        self.position = Vector(value)

    @property
    def left(self) -> Side:
        """
        The left side
        """
        return Side(self, LEFT)

    @left.setter
    def left(self, value: float):
        self.position = Vector(value + self._offset_value, self.position.y)

    @property
    def right(self) -> Side:
        """
        The right side
        """
        return Side(self, RIGHT)

    @right.setter
    def right(self, value):
        self.position = Vector(value - self._offset_value, self.position.y)

    @property
    def top(self) -> Side:
        """
        The top side
        """
        return Side(self, TOP)

    @top.setter
    def top(self, value):
        self.position = Vector(self.position.x, value - self._offset_value)

    @property
    def bottom(self) -> Side:
        """
        The bottom side
        """
        return Side(self, BOTTOM)

    @bottom.setter
    def bottom(self, value):
        self.position = Vector(self.position.x, value + self._offset_value)

    @property
    def _offset_value(self):
        return self.size / 2

    def __image__(self):
        if self.image is None:
            klass = type(self)
            prefix = Path(klass.__module__.replace('.', '/'))
            try:
                klassfile = getfile(klass)
            except TypeError:
                prefix = Path('.')
            else:
                if Path(klassfile).name != '__init__.py':
                    prefix = prefix.parent
            if prefix == Path('.'):
                self.image = ppb.Image(f"{klass.__name__.lower()}.png")
            else:
                self.image = ppb.Image(f"{prefix!s}/{klass.__name__.lower()}.png")
        return self.image
