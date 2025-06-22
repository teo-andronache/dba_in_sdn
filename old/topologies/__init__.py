# src/topologies/__init__.py

# import each topology class
from .topo_extended_star_2switches_16hosts import ExtendedStarTopo
from .topo_three_tier import ThreeTierTopo

# “from topologies import *”
__all__ = [
    "ExtendedStarTopo",
    "ThreeTierTopo",
]