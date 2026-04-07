"""Replicate Rogers' paradox by simulating evolution with people."""

import random

import six

from dallinger.config import get_config
from dallinger.experiment import Experiment
from dallinger.models import Node, Participant
from dallinger.networks import DiscreteGenerational

from operator import attrgetter

import json

max_bonus = 2.00

s = 2
g = 0.6
r = 0.55
v = 0.55

s_inc = 1
g_inc = 0.12
r_inc = 0.12
v_inc = 0.12

mutation_rate = 0.05
fitness_exponent = 3
p = 0.5


def extra_parameters():
    config = get_config()
    types = {
        "experiment_repeats": int,
        "generations": int,
        "generation_size": int,
        "bonus_payment": float,
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
        self.known_classes["AnswerCorrectness"] = self.models.AnswerCorrectness
        self.known_classes["ParentInfo"] = self.models.ParentInfo
        self.known_classes["CulturalInheritance"] = self.models.CulturalInheritance

        if session and not self.networks():
            self.setup()

    def configure(self): # contains a lot of outdated stuff
        config = get_config()
        self.experiment_repeats = config.get("experiment_repeats")
        self.generation_size = config.get("generation_size")
        self.generations = config.get("generations")
        self.bonus_payment = config.get("bonus_payment")
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
            env.create_information()
            seq_a = self.models.CorrectSequenceA( # generate a canonical sequence for the whole network
            origin=env,
            contents=json.dumps(self.random_sequence(length=11)),
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
            info = max( # why max?
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

    def create_node(self, network, participant):
        """Make a new node for participants."""
        generation = self.generation_for_new_node(network)        
        
        node = self.models.RogersAgent(network=network, participant=participant)

        print("Create_node generation:", generation) # debugging purposes
        node.generation = generation
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
        alleles = self.node_alleles(node) # maybe change?
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
        # what's the point of getting the one with the highest id? and can this be a problem if getting parent nodes?
        return json.loads(info.contents)

    def node_social_info(self, node):
        """Return social info dict for a node."""
        info = max(node.infos(type=self.models.CulturalInheritance), key=attrgetter("id"))
        return json.loads(info.contents)

    def mutate_s(self, s_value, mutation_rate=0.01, s_inc=1):
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
        # Generation 0 defaults
        if generation == 0:
            return {
                "s": s,
                "g": g,
                "r": r,
                "v": v,
            }

        parent1 = None
        parent2 = None


        if parents["Parent1_id"] is not None:
            parent1 = self.models.RogersAgent.query.get(parents["Parent1_id"])
        if parents["Parent2_id"] is not None:
            parent2 = self.models.RogersAgent.query.get(parents["Parent2_id"])

        if parent1 is None or parent2 is None:
            return{
                "s": s,
                "g": g,
                "r": r,
                "v": v,
            }

        a1 = self.node_alleles(parent1)
        a2 = self.node_alleles(parent2)

        # for each allele, inherit from one of the parents
        s_parent = random.choice([a1, a2])
        g_parent = random.choice([a1, a2])
        r_parent = random.choice([a1, a2])
        v_parent = random.choice([a1, a2])

        child_s = int(s_parent["s"]) # should be int?
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
        print("choose_parents generation:", generation)
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

        parent = random.choice(possible_parents) # allo social info comes from the same parent right now
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
            node.score = node.score + result["num_correct"] # adding correct answers to node's score

            payload = json.loads(info.contents)
            timestep = payload["timestep"]
            lifespan_l = payload["lifespanL"]

            if timestep >= lifespan_l:
                node.fitness = self.compute_fitness(node, lifespan_l, fitness_exponent) # if last timestep in lifespan, compute fitness
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

    # def recruit(self):
    #     """Recruit only the number of participants actually needed."""
    #     finished_nodes = self.models.RogersAgent.query.filter(
    #     self.models.RogersAgent.property1.isnot(None), # fitness stored here
    #     self.models.RogersAgent.failed == False
    #     ).all()
    #     num_finished = len(finished_nodes)

    #     total_needed = self.generations * self.generation_size
    #     if num_finished >= total_needed:
    #         self.log("All generations complete: closing recruitment", "-----")
    #         self.recruiter.close_recruitment()
    #         return

    #     # How many generations are unlocked?
    #     # Generation 0 is open at the start.
    #     generations_unlocked = 1 + (num_finished // self.generation_size)
    #     generations_unlocked = min(generations_unlocked, self.generations)

    #     target_participants = generations_unlocked * self.generation_size

    #     # Count how many participant nodes already exist
    #     existing_nodes = self.models.RogersAgent.query.filter_by(failed=False).all()
    #     num_existing = len(existing_nodes)

    #     shortfall = target_participants - num_existing

    #     if shortfall > 0:
    #         self.log(f"Recruiting {shortfall} participant(s)", "-----")
    #         self.recruiter.recruit(n=shortfall)


    def bonus(self, participant): # Rogers
        """Calculate a participants bonus."""
        node = participant.nodes()[0]
        if node.score is None:
            return 0.0

        bonus = min(0.02 * float(node.score), max_bonus) # should cap bonus
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

        answer_correctness = [] # new
        num_correct = 0
        num_correct += (11 - to_solve) # give points for pre-solved positions
        feedback_positions = []
        feedback_correctness = {}
        for i in range(11 - to_solve): # new
            answer_correctness.append("Correct")
        for i in range(to_solve):
            is_correct = answers[i] == correct_sequence[i]
            if is_correct:
                num_correct += 1 # wanna add something here where we record if they got answers correct
                answer_correctness.append("Correct") # new
            else: # new
                answer_correctness.append("Incorrect")
            if random.random() < learning_speed:
                feedback_positions.append(i)
                feedback_correctness[i] = is_correct

        self.models.AnswerCorrectness(
            origin=node,
            contents=json.dumps([payload, {"Answer_correctness": answer_correctness, "num_correct": num_correct}])
            )

        return {
        "num_correct": num_correct,
        "feedback_positions": feedback_positions,
        "feedback_correctness": feedback_correctness,
        "generalized_positions": generalized_positions
        }

    def add_node_to_network(self, node, network):
        """Add participant's node to a network."""
        network.add_node(node)
        node.receive()

        environment = network.nodes(type=self.models.RogersEnvironment)[0]
        environment.connect(whom=node)

        # NEW: transmit the task encounter spec
        spec = {
        "task": random.choice(["A", "B"]),
        "required_positions": list(range(6)),  # placeholder; specialization comes later
        "n_positions": 11,
        }
        encounter = self.models.TaskEncounter(origin=environment, contents=json.dumps(spec))
        environment.transmit(what=self.models.TaskEncounter, to_whom=node)

        node.receive()
        self.create_timestep_info(node)

    def compute_fitness(self, node, lifespan_l, exponent=3):
        """Compute end-of-lifespan fitness from score and allele costs."""
        alleles = self.node_alleles(node)

        g = float(alleles["g"])
        r = float(alleles["r"])
        v = float(alleles["v"])

        score = float(node.score or 0)

        cost_term = 0.1 * lifespan_l * (g + r + v)
        baseline = 0.0001

        return max(baseline, score - cost_term) ** exponent

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
        s = int(alleles["s"]) # should be int?
        g = float(alleles["g"])

        task = "A" if random.random() < p else "B" 

        if task == "A":
            to_solve = int(round(6 - s)) # should not use round function I think
        else:
            to_solve = int(round(6 + s))

        to_solve = max(1, min(11, to_solve))

        n_generalized = int(round(g * (6 - abs(s))))
        n_generalized = max(0, n_generalized)
        generalized_positions = list(range(n_generalized))

        transmission = self.transmitted_info_for_timestep(node, task, to_solve)

        return {
            "task": task,
            "toSolve": to_solve,
            "generalized_positions": generalized_positions,
            "transmitted_positions": transmission["transmitted_positions"],
            "transmitted_answers": transmission["transmitted_answers"],
        }

    def create_timestep_info(self, node):
        payload = self.build_timestep_payload(node)
        print("Creating timestep info for node") # temp
        self.models.TimestepInfo(
        origin=node,
        contents=json.dumps(payload)
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
