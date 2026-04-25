import random
from operator import attrgetter

from sqlalchemy import Float, Integer
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

from dallinger.information import Gene, State
from dallinger.models import Info
from dallinger.nodes import Agent, Source
from dallinger.networks import DiscreteGenerational

import json




class NodeAlleles(Info):
    __mapper_args__ = {"polymorphic_identity": "node_alleles"}

class CorrectSequenceA(State):
    """Canonical correct sequence for Task A within a network."""
    __mapper_args__ = {"polymorphic_identity": "correct_sequence_a"}

class CorrectSequenceB(State):
    """Canonical correct sequence for Task B within a network."""
    __mapper_args__ = {"polymorphic_identity": "correct_sequence_b"}

class FeedbackInfo(Info):
    __mapper_args__ = {"polymorphic_identity": "feedback_info"}

class AnswerCorrectness(Info):
    __mapper_args__ = {"polymorphic_identity": "answer_correctness"}

class ParentInfo(Info):
    __mapper_args__ = {"polymorphic_identity": "parent_info"}

class CulturalInheritance(Info):
    __mapper_args__ = {"polymorphic_identity": "cultural_inheritance"}

class TaskAnswer(Info):
    """Participant's answer at a timestep stored as JSON string in contents."""
    __mapper_args__ = {"polymorphic_identity": "task_answer"}

class TimestepInfo(Info):
    __mapper_args__ = {"polymorphic_identity": "timestep_info"}

class OtherInfo(Info):
    """Info regarding task that participants don't have to solve at the current timestep"""
    __mapper_args__ = {"polymorphic_identity": "other_info"}


class RogersAgent(Agent):
    """The Rogers Agent."""

    __mapper_args__ = {"polymorphic_identity": "rogers_agent"}

    @hybrid_property
    def fitness(self):
        if self.property1 is None:
            return None
        return float(self.property1)

    @fitness.setter
    def fitness(self, fitness):
        self.property1 = repr(fitness)

    @fitness.expression
    def fitness(self):
        return cast(self.property1, Float)

    @hybrid_property
    def generation(self):
        """Convert property2 to generation."""
        return int(self.property2)

    @generation.setter
    def generation(self, generation):
        """Make generation settable."""
        self.property2 = repr(generation)

    @generation.expression
    def generation(self):
        """Make generation queryable."""
        return cast(self.property2, Integer)

    @hybrid_property
    def score(self):
        """Convert property3 to score."""
        if self.property3 is None:
            return 0
        return int(self.property3)

    @score.setter
    def score(self, score):
        """Mark score settable."""
        self.property3 = repr(score)

    @score.expression
    def score(self):
        """Make score queryable."""
        return cast(self.property3, Integer)


class DiscreteGeneration(DiscreteGenerational):
    __mapper_args__ = {"polymorphic_identity": "discrete_generational"}
    
    @hybrid_property
    def complexity(self):
        return float(self.property3)

    @complexity.setter
    def complexity(self, val):
        self.property3 = repr(val)

    @complexity.expression
    def complexity(self):
        return cast(self.property3, Float)


class RogersEnvironment(Source):
    """The Rogers environment."""

    __mapper_args__ = {"polymorphic_identity": "rogers_environment"}

    

    def _info_type(self):
        """By default create States."""
        return State

    def _contents(self):
        """Contents of created infos is either proportion or 1-proportion by default."""
        return None
