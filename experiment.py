"""Replicate Rogers' paradox by simulating evolution with people."""

import random

import six

from dallinger.config import get_config
from dallinger.experiment import Experiment
from dallinger.models import Node, Participant
from dallinger.experiment_server.experiment_server import assign_properties

from operator import attrgetter

import json

import numpy as np

max_bonus = 2.00

min_s = 0
max_s = 5
s_inc = 1

min_r = 0
max_r = 1
r_inc = 0.05

min_g = 0
max_g = 1
g_inc = 0.05

min_v = 0
max_v = 1
v_inc = 0.05


range_s = np.arange(min_s, max_s + s_inc, s_inc)
range_r = np.arange(min_r, max_r + r_inc, r_inc)
range_g = np.arange(min_g, max_g + g_inc, g_inc)
range_v = np.arange(min_v, max_v + v_inc, v_inc)


mutation_rate = 0.05
fitness_exponent = 3
p_values = [0.5, 0.5, 0.5, 0.9, 0.9]
lifespan_values = [8, 2, 13, 8, 2]

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

    def __init__(self, session=None, no_configure=False):
        """Call the same function in the super (see experiments.py in dallinger).

        The models module is imported here because it must be imported at
        runtime.

        A few properties are then overwritten.

        Finally, setup() is called.
        """
        super(RogersExperiment, self).__init__(session, no_configure=no_configure)
        from . import models

        self.models = models
        self.known_classes["RogersAgent"] = self.models.RogersAgent
        self.known_classes["TaskAnswer"] = self.models.TaskAnswer
        self.known_classes["FeedbackInfo"] = self.models.FeedbackInfo
        self.known_classes["TimestepInfo"] = self.models.TimestepInfo
        self.known_classes["OtherInfo"] = self.models.OtherInfo
        self.known_classes["AnswerCorrectness"] = self.models.AnswerCorrectness
        self.known_classes["ParentInfo"] = self.models.ParentInfo
        self.known_classes["CulturalInheritance"] = self.models.CulturalInheritance
        self.known_classes["Specialization"] = self.models.Specialization
        self.known_classes["Generalization"] = self.models.Generalization
        self.known_classes["VerticalTransmission"] = self.models.VerticalTransmission
        self.known_classes["LearningSpeed"] = self.models.LearningSpeed

        if session and not self.networks():
            self.setup()

    def configure(self): 
        config = get_config()
        self.experiment_repeats = config.get("experiment_repeats")
        self.generation_size = config.get("generation_size")
        self.generations = config.get("generations")
        self.initial_recruitment_size = self.generation_size

    @property 
    def public_properties(self):
        return {
            "experiment_repeats": self.experiment_repeats,
        }

    def setup(self):
        """First time setup."""
        super(RogersExperiment, self).setup()

        for net in self.networks():
            net.max_size = net.max_size + 1  # make room for environment node.
            net.complexity = p_values[int(net.id) - 1]
            net.lifespan = lifespan_values[int(net.id) - 1]
            env = self.models.RogersEnvironment(network=net)
            self.models.CorrectSequenceA( # generate a canonical sequence for the whole network
            origin=env,
            contents=json.dumps(self.random_sequence(length=11)), # store it as info
            )
            self.models.CorrectSequenceB( 
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
        network = self.models.DiscreteGeneration(
            generations=self.generations,
            generation_size=self.generation_size,
            initial_source=False,
        )

        status = {
            "unfailed_nodes": 0,
            "completed_nodes": 0,
            "ready_for_next_gen": "No",
            "last_completed_gen": None
        }
        network.status = json.dumps(status)
        
        return network
    
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

        if not networks_participated_in:
            # if they have't started yet, assign them properties
            assign_properties(participant)
            participant.points = 0
            existing_participants = [
                ppt for ppt in self.session.query(Participant)
                .filter_by(failed=False)
                .all()
            ]

            ppt_generation = int((len(existing_participants) - 1) / int(self.generation_size))
            participant.ppt_generation = ppt_generation

            num_ppts_in_gen = len([p for p in existing_participants if p.ppt_generation == participant.ppt_generation and p.id != participant.id])
            participant.generation_pos = num_ppts_in_gen + 1

            if participant.generation_pos > self.generation_size:
                return None


        legal_networks = [
            net for net in networks_with_space if net.id not in networks_participated_in
        ]

        if not legal_networks:
            self.log("No networks available, returning None", key)
            return None
        
        else:
            return random.choice(legal_networks)
        


    def create_node(self, network, participant):
        """Make a new node for participants."""
  
        node = self.models.RogersAgent(network=network, participant=participant)
        print("??create_node called. Network: ", network, "node: ", node)

        return node
    
    def node_post_request(self, participant, node):
        """Assign properties to the node, give it its alleles, and start the timestp"""

        if node.generation == 0:
            rng = np.random.default_rng()
            
            s = int(min(5, rng.choice(range_s)))
            self.models.Specialization(
                origin=node,
                contents=s
            )

            g = float(min(1, rng.choice(range_g)))
            self.models.Generalization(
                origin=node,
                contents=g
            )

            r = float(min(1, rng.choice(range_r)))
            self.models.LearningSpeed(
                origin=node,
                contents=r
            )

            v = float(min(1, rng.choice(range_v)))
            self.models.VerticalTransmission(
                origin=node,
                contents=v
            )


            cultural_info = {
                "transmitted_positions_a": [],
                "transmitted_answers_a": {},
                "transmitted_positions_b": [],
                "transmitted_answers_b": {}
            }
            # they won't get cultural inheritnac since they're not receiving info (update creates their cultural inheritanc info)
            # so we create it here manually
            self.models.CulturalInheritance(
                origin=node,
                contents=json.dumps(cultural_info) # record what social info they see 
            ) 

        else:
            node.receive()
            print("Node received some info")
        
        node.score = 0 # start with a score of 0

        self.create_timestep_info(node)

    

    def add_node_to_network(self, node, network):
        """Add participant's node to a network."""

        node.lifespan = network.lifespan

        status = json.loads(network.status)
        status["unfailed_nodes"] += 1
        status["ready_for_next_gen"] = "No"
        network.status = json.dumps(status)
        
        network.add_node(node)


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


    def node_alleles(self, node):
        """Return allele dict for a node."""
        s_info = max(node.infos(type=self.models.Specialization), key=attrgetter("id"))
        s = int(s_info.contents)

        g_info = max(node.infos(type=self.models.Generalization), key=attrgetter("id"))
        g = float(g_info.contents)

        v_info = max(node.infos(type=self.models.VerticalTransmission), key=attrgetter("id"))
        v = float(v_info.contents)

        r_info = max(node.infos(type=self.models.LearningSpeed), key=attrgetter("id"))
        r = float(r_info.contents)

        return {
            "s": s,
            "g": g,
            "r": r,
            "v": v
        }

    def node_social_info(self, node):
        """Return social info dict for a node."""
        info = max(node.infos(type=self.models.CulturalInheritance), key=attrgetter("id"))
        return json.loads(info.contents)

    

    def inherit_social_info(self, node, A_info, B_info, parent):
        
        parent_alleles = self.node_alleles(parent)
        parent_s = int(parent_alleles["s"])
        
        if A_info is None:
            parent_correctness_a = {}
            par_to_solve_a = 6 - parent_s
            for i in range(par_to_solve_a):
                parent_correctness_a[i] = None

            for i in range(par_to_solve_a, 11):
                parent_correctness_a[i] = True

        else:
            A_info_full = json.loads(A_info.contents)
            A_correctness = A_info_full["Answer_correctness"]
            parent_correctness_a = {}
            for i in range(len(A_correctness)):
                parent_correctness_a[i] = A_correctness[i]

        if B_info is None:
            parent_correctness_b = {}
            par_to_solve_b = 6 + parent_s
            for i in range(par_to_solve_b):
                parent_correctness_b[i] = None

            for i in range(par_to_solve_b, 11):
                parent_correctness_b[i] = True

        else:
            B_info_full = json.loads(B_info.contents)
            B_correctness = B_info_full["Answer_correctness"]
            parent_correctness_b = {}
            for i in range(len(B_correctness)):
                parent_correctness_b[i] = B_correctness[i]
        
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
            if parent_correctness_a[i] is None:
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
            if parent_correctness_b[i] is None:
                continue

            if random.random() < v:
                transmitted_positions_b.append(i)

                if parent_correctness_b[i]:
                    transmitted_answers_b[i] = offspring_correct_sequence_b[i]
                else:
                    transmitted_answers_b[i] = self.random_wrong_answer(
                    offspring_correct_sequence_b[i]
                    )


        cultural_inheritance =  {
            "transmitted_positions_a": transmitted_positions_a,
            "transmitted_answers_a": transmitted_answers_a,
            "transmitted_positions_b": transmitted_positions_b,
            "transmitted_answers_b": transmitted_answers_b,
            "teacher_parent": parent.id
        }

        self.models.CulturalInheritance(
            origin=node,
            contents=json.dumps(cultural_inheritance) # record what social info they see 
        )


    
    def info_post_request(self, node, info):
        if isinstance(info, self.models.TaskAnswer):
            result = self.score_task_answer(node, info)

            if node.property3 is None:
                node.property3 = "0"
            node.score = node.score + result["num_correct"] # adding correct answers to node's score

            if node.participant.points is None:
                node.participant.points = "0"
            node.participant.points += result["answered_correct"] # adding positions the participants got correct

            payload = json.loads(info.contents)
            timestep = payload["timestep"]
            lifespan = int(payload["lifespan"])

            if timestep >= lifespan:
                node.fitness = self.compute_fitness(node, lifespan, fitness_exponent, cog_cost) # if last timestep in lifespan, compute fitness
                status = json.loads(node.network.status)
                status["completed_nodes"] +=1
                generation = node.generation
                network_nodes = node.network.nodes(type=self.models.RogersAgent)
                horizontal_nodes = [n for n in network_nodes if n.generation == generation and not n.failed and n.fitness is not None]
                if len(horizontal_nodes) < self.generation_size:
                    status["ready_for_next_gen"] = "No"
                else:
                    status["last_completed_gen"] = generation + 1
                    if generation + 1 == self.generations:
                        status["ready_for_next_gen"] = "Complete"
                    else:
                        status["ready_for_next_gen"] = "Yes"
                node.network.status = json.dumps(status)
            else:
                self.create_timestep_info(node)


            feedback_payload = {
                "timestep": timestep,
                "feedback_positions": result["feedback_positions"],
                "feedback_correctness": result["feedback_correctness"],
                "num_feedback_positions": int(len(result["feedback_positions"]))
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

        networks = self.models.DiscreteGeneration.query.all()

        complete = all(json.loads(net.status)["ready_for_next_gen"] == "Complete" for net in networks)
        end_of_generation = all(json.loads(net.status)["ready_for_next_gen"] == "Yes" for net in networks)

        if complete:
            self.log("All generations complete: closing recruitment", "-----")
            self.recruiter.close_recruitment()
            return

        elif end_of_generation:
            self.log("Generation finished, recruiting next generation")
            self.recruiter.recruit(n=int(self.generation_size))


    def bonus(self, participant):
        """Calculate a participants bonus."""

        bonus = min(0.02 * float(participant.points), max_bonus) # should cap bonus
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
        num_correct += (11 - to_solve) # give points for pre-solved positions. num_correct is used for fitness
        answered_correct = 0 # how many they actually answered correct (does not count pre-solved positions). This is for bonus calculation
        feedback_positions = []
        feedback_correctness = {}
        for i in range(to_solve):
            is_correct = answers[i] == correct_sequence[i]
            if is_correct:
                num_correct += 1 # wanna add something here where we record if they got answers correct
                answer_correctness.append(True)
                answered_correct += 1
            else: 
                answer_correctness.append(False)
            if random.random() < learning_speed:
                feedback_positions.append(i)
                feedback_correctness[i] = is_correct
        
        for i in range(11 - to_solve):
            answer_correctness.append(True)

        self.models.AnswerCorrectness(
            origin=node,
            contents=json.dumps({"timestep": payload["timestep"],"task": task,"Answer_correctness": answer_correctness, "num_correct": num_correct, "Individually_correct_answer": correct_sequence}),
            details=task
            )

        return {
        "num_correct": num_correct,
        "feedback_positions": feedback_positions,
        "feedback_correctness": feedback_correctness,
        "generalized_positions": generalized_positions,
        "answered_correct": answered_correct,
        "Individually_correct_answer": correct_sequence,
        "Answer_correctness": answer_correctness
        }


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


    def build_info_for_timestep(self, node):
        """Build one timestep's information for the frontend"""
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
        task_A, task_B = self.build_info_for_timestep(node)
        
        p = float(node.network.complexity)
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

    
    def fail_participant(self, participant):
        """Fail all the nodes of a participant."""
        participant_nodes = Node.query.filter_by(
            participant_id=participant.id, failed=False
        ).all()

        print("??fail_participant called for Participant ", participant.id)
        for node in participant_nodes:
            infos = node.infos()
            for info in infos:
                info.fail()
            node.fail()
            status = json.loads(node.network.status)
            status["ready_for_next_gen"] = "No"
            status["unfailed_nodes"] -= 1
            if node.fitness is not None:
                status["completed_nodes"] -= 1
            node.fitness = None
            node.network.status = json.dumps(status)
        self.session.commit()

    
    def data_check(self, participant):
        print("??checking data for Participant ", participant.id)
        participant_nodes = Node.query.filter_by(
            participant_id=participant.id).all()

        for node in participant_nodes:
            if node.failed:
                return False
            if len(node.infos(type=self.models.AnswerCorrectness)) != int(node.lifespan):
                print("Node ", node.id, " for Participant ", participant.id, " has bad data")
                return False
        return True