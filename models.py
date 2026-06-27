import random
from operator import attrgetter

from sqlalchemy import Float, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

from dallinger.information import Gene, State
from dallinger.models import Info, Participant
from dallinger.nodes import Agent, Source
from dallinger.networks import DiscreteGenerational
from . import experiment

import json




class Specialization(Gene):
    __mapper_args__ = {"polymorphic_identity": "specialization"}

    def _mutated_contents(self, mutation_rate=0.05, s_inc=1):
        """The mutated contents of an info."""
        s_value = int(self.contents)
        
        draw = random.random()

        if draw < mutation_rate:
            s_value -= s_inc
        elif draw > 1.0 - mutation_rate:
            s_value += s_inc

        return max(-5, min(5, s_value))
        

class Generalization(Gene):
    __mapper_args__ = {"polymorphic_identity": "generalization"}

    def _mutated_contents(self, sd=0.05):
        """Mutate according to a normal distribution. sd is the g_inc."""
        value = float(self.contents)
        value = value + random.gauss(0, sd)
        return max(0.0, min(1.0, value))

class VerticalTransmission(Gene):
    __mapper_args__ = {"polymorphic_identity": "vertical_transmission"}

    def _mutated_contents(self, sd=0.05):
        """Mutate according to a normal distribution. sd is the v_inc."""
        value = float(self.contents)
        value = value + random.gauss(0, sd)
        return max(0.0, min(1.0, value))

class LearningSpeed(Gene):
    __mapper_args__ = {"polymorphic_identity": "learning_speed"}

    def _mutated_contents(self, sd=0.05):
        """Mutate according to a normal distribution. sd is the r_inc."""
        value = float(self.contents)
        value = value + random.gauss(0, sd)
        return max(0.0, min(1.0, value))

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
    
    @hybrid_property
    def lifespan(self):
        """Convert property4 to lifespan."""
        return int(self.property4)

    @lifespan.setter
    def lifespan(self, lifespan):
        self.property4 = repr(lifespan)

    @lifespan.expression
    def lifespan(self):
        return cast(self.property4, Integer)
    

    @hybrid_property
    def parents(self):
        """Convert property5 to parents."""
        return self.property5

    @parents.setter
    def parents(self, parents):
        self.property5 = repr(parents)

    @parents.expression
    def parents(self):
        return cast(self.property5, String)
    

    def update(self, infos):
        """Process received infos.

        Update controls the default behavior of a node when it receives infos.
        By default it does nothing.
        """

        print("Update called. Infos: ", infos)
        # check self is not failed
        if self.failed:
            raise ValueError("{} cannot update as it has failed.".format(self))
        
        parent_s = [s for s in infos if s.type == "specialization"]
        parent_g = [g for g in infos if g.type == "generalization"]
        parent_v = [v for v in infos if v.type == "vertical_transmission"]
        parent_r = [r for r in infos if r.type == "learning_speed"]

        # now that we have the infos that were transmitted to them, we need to use it/save it. For the alleles, for each allele they
        # need to randomly pick one of the parent's alleles and mutate it. 

        self.mutate(random.choice(parent_s))
        self.mutate(random.choice(parent_g))
        self.mutate(random.choice(parent_v))
        self.mutate(random.choice(parent_r))

        social_info = [s for s in infos if s.type == "answer_correctness"]
        parents = list({s.origin for s in social_info})
        teacher_parent = random.choice(parents)
        A_info = next((a for a in social_info if a.details == "A" and a.origin == teacher_parent), None)
        B_info = next((b for b in social_info if b.details == "B" and b.origin == teacher_parent), None)
        exp = experiment.RogersExperiment()
        exp.inherit_social_info(node = self, A_info = A_info, B_info = B_info, parent = teacher_parent)



@hybrid_property
def points(self):
    """Convert property1 to points."""
    if self.property1 is None:
        return 0
    return int(self.property1)

@points.setter
def points(self, points):
    """Mark points settable."""
    self.property1 = repr(points)

@points.expression
def points(self):
    """Make points queryable."""
    return cast(self.property1, Integer)
Participant.points = points

@hybrid_property
def ppt_generation(self):
    """Convert property2 to the participant generation."""
    return int(self.property2)

@ppt_generation.setter
def ppt_generation(self, ppt_generation):
    self.property2 = repr(ppt_generation)

@ppt_generation.expression
def ppt_generation(self):
    return cast(self.property2, Integer)
Participant.ppt_generation = ppt_generation


@hybrid_property
def generation_pos(self):
    """Convert property3 to the participant's position in a generation."""
    return int(self.property3)

@generation_pos.setter
def generation_pos(self, generation_pos):
    self.property3 = repr(generation_pos)

@generation_pos.expression
def generation_pos(self):
    return cast(self.property3, Integer)
Participant.generation_pos = generation_pos
    

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
    
    @hybrid_property
    def lifespan(self):
        """Convert property4 to lifespan."""
        return int(self.property4)

    @lifespan.setter
    def lifespan(self, lifespan):
        self.property4 = repr(lifespan)

    @lifespan.expression
    def lifespan(self):
        return cast(self.property4, Integer)
    
    @hybrid_property
    def status(self):
        return self.property5

    @status.setter
    def status(self, val):
        self.property5 = val

    @status.expression
    def status(self):
        return cast(self.property5, String)
    
    def add_node(self, node):
        """Link to the agent from a parent based on the parent's fitness"""
        num_agents = len(self.nodes(type=RogersAgent))
        curr_generation = int((num_agents - 1) / float(self.generation_size))
        node.generation = curr_generation # !!!! Will maybe want generation to come from participant?

        if curr_generation == 0:
            parent1 = None
            parent2 = None
            node.parents = json.dumps({"Parent_1": None, "Parent_2": None})
        else:
            parent1 = self._select_fit_node_from_generation(
                node_type=RogersAgent, generation=curr_generation - 1
            )
            parent2 = self._select_fit_node_from_generation(
                node_type=RogersAgent, generation=curr_generation - 1
            )

            tries = 0
            while parent2.id == parent1.id and tries < 50: # potentially worth it
                parent2 = self._select_fit_node_from_generation(
                node_type=RogersAgent, generation=curr_generation - 1
                )
                tries += 1
            
            node.parents = json.dumps({"Parent_1": parent1.id, "Parent_2": parent2.id})

        if parent1 is not None and parent2 is not None:
            # can transmit both alleles and social info here. In the add_node_to_network function in experiment.py, you need to say that
            # if generation == 0, then have some random value for the alleles, and no social info

            # if we have them transmit answer correctness, the the children will just have the importnat info they need, right?
            parent1.connect(whom=node)
            parent1.transmit(to_whom=node, what=[Specialization, Generalization, VerticalTransmission, LearningSpeed])
            p1_answer_infos = parent1.infos(type=AnswerCorrectness)
            p1_A_infos = [i for i in p1_answer_infos if i.details == "A"]
            p1_B_infos = [i for i in p1_answer_infos if i.details == "B"]
            if len(p1_A_infos) >= 1:
                parent1.transmit(to_whom=node, what=max(p1_A_infos, key=attrgetter("id")))
            
            if len(p1_B_infos) >= 1:
                parent1.transmit(to_whom=node, what=max(p1_B_infos, key=attrgetter("id"))) 

            parent2.connect(whom=node)
            parent2.transmit(to_whom=node, what=[Specialization, Generalization, VerticalTransmission, LearningSpeed])
            p2_answer_infos = parent2.infos(type=AnswerCorrectness)
            p2_A_infos = [i for i in p2_answer_infos if i.details == "A"]
            p2_B_infos = [i for i in p2_answer_infos if i.details == "B"]
            if len(p2_A_infos) >= 1:
                parent2.transmit(to_whom=node, what=max(p2_A_infos, key=attrgetter("id")))
            
            if len(p2_B_infos) >= 1:
                parent2.transmit(to_whom=node, what=max(p2_B_infos, key=attrgetter("id"))) 
    

    def _select_fit_node_from_generation(self, node_type, generation):
        prev_agents = node_type.query.filter_by(
            failed=False, network_id=self.id, generation=(generation),
        ).all()
        prev_fits = [p.fitness for p in prev_agents if p.fitness is not None]
        prev_probs = [(f / (1.0 * sum(prev_fits))) for f in prev_fits]

        rnd = random.random()
        temp = 0.0
        for i, probability in enumerate(prev_probs):
            temp += probability
            if temp > rnd:
                return prev_agents[i]
            





class RogersEnvironment(Source):
    """The Rogers environment."""

    __mapper_args__ = {"polymorphic_identity": "rogers_environment"}

    

    def _info_type(self):
        """By default create States."""
        return State

    def _contents(self):
        """Contents of created infos is either proportion or 1-proportion by default."""
        return None
