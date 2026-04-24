"""Replicate Rogers' paradox by simulating evolution with people."""

import random

import six

from dallinger.config import get_config
from dallinger.experiment import Experiment
from dallinger.models import Node, Participant
from dallinger.networks import DiscreteGenerational

from operator import attrgetter

import json

import numpy as np

max_bonus = 2.00

min_s = 0
max_s = 5
s_inc = 1

min_r = 0
max_r = 1
r_inc = 0.12

min_g = 0
max_g = 1
g_inc = 0.12

min_v = 0
max_v = 1
v_inc = 0.12


range_s = np.arange(min_s, max_s + s_inc, s_inc)
range_r = np.arange(min_r, max_r + r_inc, r_inc)
range_g = np.arange(min_g, max_g + g_inc, g_inc)
range_v = np.arange(min_v, max_v + v_inc, v_inc)


mutation_rate = 0.05
fitness_exponent = 3
p = 0.5

cog_cost = 0.1


def extra_parameters():
    config = get_config()
    types = {
        "experiment_repeats": int,
        "generations": int,
        "generation_size": int
    }

    for key in types:
        config.register(key, types[key])


class RogersExperiment(Experiment):
    """The experiment class."""

    def __init__(self, session=None):
        """Call the same function in the super (see experiments.py in dallinger).

        The models module is imported here because it must be imported at
        runtime.

        A few properties are then overwritten.

        Finally, setup() is called.
        """
        super(RogersExperiment, self).__init__(session)
        from . import models

        self.models = models
        self.known_classes["TaskAnswer"] = self.models.TaskAnswer
        self.known_classes["NodeAlleles"] = self.models.NodeAlleles
        self.known_classes["FeedbackInfo"] = self.models.FeedbackInfo
        self.known_classes["TimestepInfo"] = self.models.TimestepInfo
        self.known_classes["OtherInfo"] = self.models.OtherInfo
        self.known_classes["AnswerCorrectness"] = self.models.AnswerCorrectness
        self.known_classes["ParentInfo"] = self.models.ParentInfo
        self.known_classes["CulturalInheritance"] = self.models.CulturalInheritance

        if session and not self.networks():
            self.setup()

    def configure(self): 
        config = get_config()
        self.experiment_repeats = config.get("experiment_repeats")
        self.generation_size = config.get("generation_size")
        self.generations = config.get("generations")
        self.initial_recruitment_size = self.generation_size

    @property # probably not useful
    def public_properties(self):
        return {
            "experiment_repeats": self.experiment_repeats,
        }

    def setup(self):
        """First time setup."""
        super(RogersExperiment, self).setup()

        for net in self.networks():
            net.max_size = net.max_size + 1  # make room for environment node.
            env = self.models.RogersEnvironment(network=net)
            seq_a = self.models.CorrectSequenceA( # generate a canonical sequence for the whole network
            origin=env,
            contents=json.dumps(self.random_sequence(length=11)), # store it as info
            )
            seq_b = self.models.CorrectSequenceB( 
            origin=env,
            contents=json.dumps(self.random_sequence(length=11)),
            )

        self.session.commit()
    
    def random_sequence(self, length=11):
        """Generate a random correct sequence of arrow responses."""
        return [
            random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
            for i in range(length)
        ]

    def correct_sequence_for_task(self, node, task): 
        """Return the correct sequence for task A or B in for a network."""
        env = node.network.nodes(type=self.models.RogersEnvironment)[0]
        if task == "A":
            info = max(
            env.infos(type=self.models.CorrectSequenceA),
            key=attrgetter("id"),
            )
        elif task == "B":
            info = max(
            env.infos(type=self.models.CorrectSequenceB),
            key=attrgetter("id"),
            )
        else:
            raise ValueError("Unknown task: {}".format(task))
        return json.loads(info.contents)


    def create_network(self):
        """Create a new network."""
        return DiscreteGenerational(
            generations=self.generations,
            generation_size=self.generation_size,
            initial_source=False,
        )
    
    def get_network_for_participant(self, participant):
        """Place participant in a network depending in which they have already completed"""
        key = participant.id
        networks_with_space = self.networks(full=False)
        networks_participated_in = [
            node.network_id
            for node in Node.query.with_entities(Node.network_id)
            .filter_by(participant_id=participant.id)
            .all()
        ]

        legal_networks = [
            net for net in networks_with_space if net.id not in networks_participated_in
        ]

        if not legal_networks:
            self.log("No networks available, returning None", key)
            return None
        
        else:
            return min(legal_networks, key = attrgetter("id"))
        


    def create_node(self, network, participant):
        """Make a new node for participants."""
        alleles = {}

        generation = self.generation_for_new_node(network)        
        print("create_node called")
        node = self.models.RogersAgent(network=network, participant=participant)

        print("Create_node generation:", generation) # debugging purposes
        node.generation = generation # saving it to the node
        node.score = 0 # start with a score of 0

        parents = self.choose_parents(network, generation)
        print("create_node chosen parents", parents) # debugging

        self.models.ParentInfo(
            origin=node,
            contents=json.dumps(parents) # record info of who their parents were
        )

        alleles = self.inherit_alleles(network, generation, parents) # inherit parent alleles

        self.models.NodeAlleles(
            origin=node,
            contents=json.dumps(alleles) # store alleles
        )

        CulturalInheritance = self.inherit_social_info(node, parents)

        self.models.CulturalInheritance(
            origin=node,
            contents=json.dumps(CulturalInheritance) # record what social info they see 
        )

        return node

    def generalize(self, node): # this is where we create the actual correct answers for participants
        """Return the positions generalized between A and B for this node."""
        alleles = self.node_alleles(node)
        s = int(alleles["s"])
        g = float(alleles["g"])
        seq_a = list(self.correct_sequence_for_task(node, "A"))
        seq_b = list(self.correct_sequence_for_task(node, "B"))

        n_generalized = int(round(g * (6 - abs(s)))) # g as a proportion of more specialized task

        for i in range(n_generalized): 
            if s >= 0: # chatgpt really wants me to do it this way for some reason
                seq_b[i] = seq_a[i]   
            else:
                seq_a[i] = seq_b[i]   

        return seq_a, seq_b, list(range(n_generalized))

    
    def generation_for_new_node(self, network):
        """Return generation index for the next participant node in this network."""
        existing_agents = network.nodes(type=self.models.RogersAgent)
        return len(existing_agents) // self.generation_size 


    def parent_pool(self, network, generation):
        """Return eligible parents from the previous generation in this network."""
        if generation == 0:
            return []

        prev_gen = generation - 1
        return self.models.RogersAgent.query.filter_by(
            network_id=network.id,
            generation=prev_gen,
            failed=False,
        ).all()


    def sample_parent(self, parents):
        """Sample one parent weighted by fitness."""
        if not parents:
            return None

        weights = []
        for p in parents:
            if p.fitness is None:
                weights.append(0.0)
            else:
                weights.append(max(0.0, float(p.fitness)))

        if sum(weights) == 0:
            return random.choice(parents)

        return random.choices(parents, weights=weights, k=1)[0]


    def node_alleles(self, node):
        """Return allele dict for a node."""
        info = max(node.infos(type=self.models.NodeAlleles), key=attrgetter("id"))
        return json.loads(info.contents)

    def node_social_info(self, node):
        """Return social info dict for a node."""
        info = max(node.infos(type=self.models.CulturalInheritance), key=attrgetter("id"))
        return json.loads(info.contents)

    def mutate_s(self, s_value, mutation_rate=0.05, s_inc=1):
        """Discrete mutation for specialization"""
        draw = random.random()

        if draw < mutation_rate:
            s_value -= s_inc
        elif draw > 1.0 - mutation_rate:
            s_value += s_inc

        return max(-5, min(5, s_value))


    def mutate(self, value, sd):
        """mutate according to normal distribution. Used for g, v, and r."""
        value = value + random.gauss(0, sd)
        return max(0.0, min(1.0, value))


    def inherit_alleles(self, network, generation, parents):
        """Create offspring alleles using sexual reproduction."""
        print("inherit alleles called")
        rng = np.random.default_rng()
        # Generation 0 defaults
        if generation == 0:
            return {
                "s": int(rng.choice(range_s)),
                "g": float(rng.choice(range_g)),
                "r": float(rng.choice(range_r)),
                "v": float(rng.choice(range_v)),
            }

        parent1 = None
        parent2 = None


        if parents["Parent1_id"] is not None:
            parent1 = self.models.RogersAgent.query.get(parents["Parent1_id"])
        if parents["Parent2_id"] is not None:
            parent2 = self.models.RogersAgent.query.get(parents["Parent2_id"])

        if parent1 is None or parent2 is None:
            return{
                "s": int(np.random.choice(range_s)),
                "g": float(np.random.choice(range_g)),
                "r": float(np.random.choice(range_r)),
                "v": float(np.random.choice(range_v)),
            }

        a1 = self.node_alleles(parent1)
        a2 = self.node_alleles(parent2)

        # for each allele, inherit from one of the parents
        s_parent = random.choice([a1, a2])
        g_parent = random.choice([a1, a2])
        r_parent = random.choice([a1, a2])
        v_parent = random.choice([a1, a2])

        child_s = int(s_parent["s"]) 
        child_g = float(g_parent["g"])
        child_r = float(r_parent["r"])
        child_v = float(v_parent["v"])

        # Mutate
        child_s = self.mutate_s(child_s, mutation_rate, s_inc)
        child_g = self.mutate(child_g, g_inc)
        child_r = self.mutate(child_r, r_inc)
        child_v = self.mutate(child_v, v_inc)

        # Cultural Inheritance


        return {
            "s": child_s,
            "g": child_g,
            "r": child_r,
            "v": child_v,
        }  


    def choose_parents(self, network, generation):
        print("choose_parents generation:", generation) # debugging
        if generation == 0:
            return {
                "Parent1_id": None,
                "Parent2_id": None
            } 
          
        else:
            parents = self.parent_pool(network, generation)
        
            parent1 = self.sample_parent(parents)
            parent2 = self.sample_parent(parents)

            tries = 0
            while parent2.id == parent1.id and tries < 10: # potentially worth it
                parent2 = self.sample_parent(parents)
                tries += 1
        
            return {
                "Parent1_id": parent1.id,
                "Parent2_id": parent2.id
            }


    def inherit_social_info(self, node, parents):
        parent1 = None
        parent2 = None
        if parents["Parent1_id"] is not None:
            parent1 = self.models.RogersAgent.query.get(parents["Parent1_id"])
        if parents["Parent2_id"] is not None:
            parent2 = self.models.RogersAgent.query.get(parents["Parent2_id"])
        
        possible_parents = [p for p in [parent1, parent2] if p is not None]
        if len(possible_parents) == 0:
            return {
                "transmitted_positions_a": [],
                "transmitted_answers_a": {},
                "transmitted_positions_b": [],
                "transmitted_answers_b": {}
            }

        parent = random.choice(possible_parents) # all social info comes from the same parent right now
        if parent is None:
            return {
                "transmitted_positions_a": [],
                "transmitted_answers_a": {},
                "transmitted_positions_b": [],
                "transmitted_answers_b": {}
            }

        parent_answer_info_a = self.last_task_answer(parent, "A")
        parent_answer_info_b = self.last_task_answer(parent, "B")

        if parent_answer_info_a is not None:
            parent_correctness_a = self.parent_correctness_by_position(parent, "A", parent_answer_info_a)
        else:
            parent_correctness_a = {}
        if parent_answer_info_b is not None:
            parent_correctness_b = self.parent_correctness_by_position(parent, "B", parent_answer_info_b)
        else:
            parent_correctness_b = {}

        alleles = self.node_alleles(node)
        v = float(alleles["v"])
        s = int(alleles["s"])

        seq_a, seq_b, _ = self.generalize(node)
        offspring_correct_sequence_a = seq_a
        offspring_correct_sequence_b = seq_b

        transmitted_positions_a = []
        transmitted_answers_a = {}

        transmitted_positions_b = []
        transmitted_answers_b = {}

        to_solve_a = 6 - s
        to_solve_b = 6 + s


        # loop through A
        for i in range(to_solve_a):
            if i not in parent_correctness_a:
                continue

            if random.random() < v:
                transmitted_positions_a.append(i)

                if parent_correctness_a[i]:
                    transmitted_answers_a[i] = offspring_correct_sequence_a[i]
                else:
                    transmitted_answers_a[i] = self.random_wrong_answer(
                    offspring_correct_sequence_a[i]
                    )

        # loop through B
        for i in range(to_solve_b):
            if i not in parent_correctness_b:
                continue

            if random.random() < v:
                transmitted_positions_b.append(i)

                if parent_correctness_b[i]:
                    transmitted_answers_b[i] = offspring_correct_sequence_b[i]
                else:
                    transmitted_answers_b[i] = self.random_wrong_answer(
                    offspring_correct_sequence_b[i]
                    )


        return {
            "transmitted_positions_a": transmitted_positions_a,
            "transmitted_answers_a": transmitted_answers_a,
            "transmitted_positions_b": transmitted_positions_b,
            "transmitted_answers_b": transmitted_answers_b,
        }


    def info_post_request(self, node, info):
        if isinstance(info, self.models.TaskAnswer):
            result = self.score_task_answer(node, info)

            if node.property3 is None:
                node.property3 = "0"
            node.score = node.score + result["answered_correct"] # adding correct answers to node's score

            payload = json.loads(info.contents)
            timestep = payload["timestep"]
            lifespan = payload["lifespan"]

            if timestep >= lifespan:
                node.fitness = self.compute_fitness(node, lifespan, fitness_exponent, cog_cost) # if last timestep in lifespan, compute fitness
            else:
                self.create_timestep_info(node)

            feedback_payload = {
                "feedback_positions": result["feedback_positions"],
                "feedback_correctness": result["feedback_correctness"],
                "generalized_positions": result["generalized_positions"]
            }

            self.models.FeedbackInfo(
                origin=node,
                contents=json.dumps(feedback_payload)
            )
            self.session.commit()
            return

    def submission_successful(self, participant):
        """Called when a participant finishes."""
        self.recruit()


    def recruit(self):
        """Recruit participants for next generation."""
        finished_nodes = self.models.RogersAgent.query.filter(
        self.models.RogersAgent.fitness.isnot(None),
        self.models.RogersAgent.failed == False
        ).all()

        num_finished = len(finished_nodes)

        # generation complete when enough nodes finished
        end_of_generation = num_finished > 0 and num_finished % self.generation_size == 0

        complete = num_finished >= (self.generations * self.generation_size)

        if complete:
            self.log("All generations complete: closing recruitment", "-----")
            self.recruiter.close_recruitment()
            return

        elif end_of_generation:
            self.log("Generation finished, recruiting next generation")
            self.recruiter.recruit(n=self.generation_size)


    def bonus(self, participant): # Rogers
        """Calculate a participants bonus."""
        score_sum = 0
        for node in participant.nodes():
            if node.score is None:
                score_sum = score_sum
            else:
                score_sum += node.score

        bonus = min(0.02 * float(score_sum), max_bonus) # should cap bonus
        return round(bonus, 2)  


    def score_task_answer(self, node, info): # guessing used each time player submits taskanswer info
        payload = json.loads(info.contents) # get contents of taskanswer info

        task = payload["task"]
        to_solve = payload["toSolve"]
        answers = payload["answers"]

        alleles = self.node_alleles(node)
        learning_speed = alleles["r"]

        seq_a, seq_b, generalized_positions = self.generalize(node) # get actual correct sequence for this node

        if task == "A":
            correct_sequence = seq_a
        else:
            correct_sequence = seq_b

        answer_correctness = []
        num_correct = 0
        num_correct += (11 - to_solve) # give points for pre-solved positions
        answered_correct = 0 # how many they actually answered correct (does not count pre-solved positions)
        feedback_positions = []
        feedback_correctness = {}
        for i in range(to_solve):
            is_correct = answers[i] == correct_sequence[i]
            if is_correct:
                num_correct += 1 # wanna add something here where we record if they got answers correct
                answer_correctness.append("Correct")
                answered_correct += 1
            else: 
                answer_correctness.append("Incorrect")
            if random.random() < learning_speed:
                feedback_positions.append(i)
                feedback_correctness[i] = is_correct
        
        for i in range(11 - to_solve):
            answer_correctness.append("Correct")

        self.models.AnswerCorrectness(
            origin=node,
            contents=json.dumps([payload, {"Answer_correctness": answer_correctness, "num_correct": num_correct}])
            )

        return {
        "num_correct": num_correct,
        "feedback_positions": feedback_positions,
        "feedback_correctness": feedback_correctness,
        "generalized_positions": generalized_positions,
        "answered_correct": answered_correct
        }

    def add_node_to_network(self, node, network):
        """Add participant's node to a network."""
        network.add_node(node)
        node.receive()

        environment = network.nodes(type=self.models.RogersEnvironment)[0]
        environment.connect(whom=node)
        node.receive()
        self.create_timestep_info(node)

    def compute_fitness(self, node, lifespan, fitness_exponent=3, cog_cost=0.1):
        """Compute end-of-lifespan fitness from score and allele costs."""
        alleles = self.node_alleles(node)

        g = float(alleles["g"])
        r = float(alleles["r"])
        v = float(alleles["v"])

        score = float(node.score or 0)

        cost_term = cog_cost * (g + r + v)
        baseline = 0.0001

        return max(baseline, (score / (11*lifespan)) - cost_term) ** fitness_exponent

    def random_wrong_answer(self, correct_answer):
        """Return a random arrow that is not the correct answer."""
        options = ["UP", "DOWN", "LEFT", "RIGHT"]
        wrong_options = [x for x in options if x != correct_answer]
        return random.choice(wrong_options)
    
    def last_task_answer(self, parent, task):
        """Return the parent's most recent TaskAnswer for a given task, or None."""
        answers = []
        for info in parent.infos(type=self.models.TaskAnswer):
            payload = json.loads(info.contents)
            if payload.get("task") == task:
                answers.append(info)

        if not answers:
            return None

        return max(answers, key=attrgetter("id"))

    def parent_correctness_by_position(self, parent, task, parent_answer_info):
        """Return dict mapping positions to whether parent was correct there."""
        payload = json.loads(parent_answer_info.contents)

        to_solve = payload["toSolve"]
        answers = payload["answers"]

        seq_a, seq_b, _ = self.generalize(parent)
        if task == "A":
            correct_sequence = seq_a
        else:
            correct_sequence = seq_b

        correctness = {}

        # Pre-solved positions count as correct
        for i in range(to_solve, 11):
            correctness[i] = True

        # Answered positions
        for i in range(to_solve):
            correctness[i] = (answers[i] == correct_sequence[i])

        return correctness


    def build_timestep_payload(self, node):
        """Build one timestep's task/hint payload for the frontend."""
        alleles = self.node_alleles(node)
        s = int(alleles["s"])
        g = float(alleles["g"])

        to_solve_A = max(1, min(11, int(6 - s)))
        to_solve_B = max(1, min(11, int(6 + s)))
        
        n_generalized = int(round(g * (6 - abs(s))))
        n_generalized = max(0, n_generalized)
        generalized_positions = list(range(n_generalized))

        transmission_A = self.transmitted_info_for_timestep(node, "A", to_solve_A)
        transmission_B = self.transmitted_info_for_timestep(node, "B", to_solve_B)


        n_generalized = int(round(g * (6 - abs(s))))
        n_generalized = max(0, n_generalized)
        generalized_positions = list(range(n_generalized))

        task_A = {
            "task": "A",
            "toSolve": to_solve_A,
            "generalized_positions": generalized_positions,
            "transmitted_positions": transmission_A["transmitted_positions"],
            "transmitted_answers": transmission_A["transmitted_answers"]
        }

        task_B = {
            "task": "B",
            "toSolve": to_solve_B,
            "generalized_positions": generalized_positions,
            "transmitted_positions": transmission_B["transmitted_positions"],
            "transmitted_answers": transmission_B["transmitted_answers"]
        }

        return task_A, task_B

    def create_timestep_info(self, node):
        task_A, task_B = self.build_timestep_payload(node)
        print("Creating timestep info for node") # temp
        
        task = "A" if random.random() < p else "B"

        if task == "A":
            payload = task_A
            other_info = task_B
        else:
            payload = task_B
            other_info = task_A 
        
        self.models.TimestepInfo(
        origin=node,
        contents=json.dumps(payload)
        )

        self.models.OtherInfo(
        origin=node,
        contents=json.dumps(other_info)
        )

        self.session.commit()

    def transmitted_info_for_timestep(self, node, task, to_solve):
        """Return transmitted positions and answers for this offspring timestep."""
        social_info = self.node_social_info(node)

        if task == "A":
            transmitted_positions = social_info["transmitted_positions_a"]
            transmitted_answers = social_info["transmitted_answers_a"]
        
        else:
            transmitted_positions = social_info["transmitted_positions_b"]
            transmitted_answers = social_info["transmitted_answers_b"]

        transmitted_positions = [i for i in transmitted_positions if i < to_solve]
        transmitted_answers = {
            int(k): v for k, v in transmitted_answers.items()
            if int(k) < to_solve
        }
        
        return {
            "transmitted_positions": transmitted_positions,
            "transmitted_answers": transmitted_answers,
        }
