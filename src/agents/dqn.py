import random
import numpy as np
from copy import deepcopy

from gym import Env

import torch
import torch.nn as nn
from torch.optim import Optimizer
from torch.autograd import Variable

from src.replays import Replay, Transition


class DQN:

  REQUIRED_REPLAY_FACTOR = 10

  def __init__(self, env: Env, policy: nn.Module, replay_memory: Replay, replay_size: int,
               optimizer: Optimizer, discount_rate: float, max_epsilon: float, min_epsilon: float, epsilon_decay: float,
               target_update_steps: int):
    """
    Initialize a vanilla DQN agent.

    :param env: Gym environment for the agent to operate in.
    :param policy: Neural network to use as the policy.
    :param replay_memory: Replay memory to use.
    :param replay_size: Replay size to use while tuning the agent.
    :param optimizer: Optimizer to be used for updating parameters of the policy.
    :param discount_rate: Discount rate to be applied to the rewards collected by the agent.
    :param max_epsilon: Epsilon value to use for epsilon greedy exploration-exploitation.
    :param min_epsilon: Minimum epsilon value to maintain after annealing it.
    :param epsilon_decay: Decay rate for the exploration.
    :param target_update_steps: Number of steps to take before updating the target policy.
    """
    self.env = env
    self.policy = policy

    self.target_policy = deepcopy(self.policy)
    self.target_policy.train(False)

    self.criterion = nn.MSELoss()

    self.replay_memory = replay_memory
    self.replay_size = replay_size

    self.optimizer = optimizer
    self.discount_rate = discount_rate

    self.max_epsilon = max_epsilon
    self.epsilon = max_epsilon
    self.min_epsilon = min_epsilon
    self.epsilon_decay = epsilon_decay

    self.target_update_steps = target_update_steps
    self._steps_since_update = 0.
    pass

  def predict_q(self, state: torch.Tensor) -> torch.Tensor:
    """
    Return Q-value predictions given a particular state as input.

    :param state: State for which to predict the Q-values

    :return: torch.Tensor
    """
    with torch.no_grad():
      return self.policy(state)

  def select_action(self, state: torch.Tensor) -> int:
    """
    Select an action given the state using epsilon greedy for sampling.

    :param state: State of the environment in which we would like to predict the Q-values.

    :return: torch.Tensor
    """
    if random.random() < self.epsilon:
      return self.env.action_space.sample()

    return torch.argmax(self.predict_q(state)).item()

  def tune(self):
    """
    Replay a specific number of transitions and tune the agent's policy.

    :return: None
    """
    sampled = self.replay_memory.sample(self.replay_size)
    sampled = list(zip(*sampled))

    states, actions, rewards, next_states, is_final = sampled[0], sampled[1], sampled[2], sampled[3], sampled[4]

    states = torch.Tensor(np.array(states))
    actions_tensor = torch.Tensor(np.array(actions))
    next_states = torch.Tensor(np.array(next_states))
    rewards = torch.Tensor(np.array(rewards))

    is_final_tensor = torch.Tensor(is_final)
    is_final_indices = torch.where(is_final_tensor == True)[0]

    q_values_expected = self.policy(states)
    q_values_next = self.policy(next_states)

    q_values_expected[range(len(q_values_expected)), actions] = rewards + self.discount_rate * torch.max(q_values_next, axis=1).values
    q_values_expected[is_final_indices.tolist(), actions_tensor[is_final_indices].tolist()] = rewards[is_final_indices.tolist()]

    q_values_predicted = self.policy(states)
    loss = self.criterion(q_values_predicted, q_values_expected)

    self.optimizer.zero_grad()
    loss.backward()
    self.optimizer.step()
    pass

  def reset(self) -> None:
    """
    Reset the agent to its original state.

    :return: None
    """
    self.replay_memory.truncate()
    self.epsilon = self.max_epsilon
    pass

  def _update_target(self) -> None:
    """
    Update the parameters of the target policy.

    :return: None
    """
    self.target_policy.load_state_dict(deepcopy(self.policy.state_dict()))
    self.target_policy.train(False)
    pass

  @property
  def _required_replay_size(self) -> int:
    """
    Compute the replay memory size required for sampling in order to assure that samples are roughly iid.

    :return: int
    """
    return min(self.replay_size * self.REQUIRED_REPLAY_FACTOR, self.replay_memory.capacity)

  def _anneal_epsilon(self):
    """
    Anneal the value of epsilon given the epsilon decay rate.

    :return: None
    """
    if self.epsilon > self.min_epsilon:
      self.epsilon = self.epsilon - self.epsilon_decay

  def play_episode(self, tune: bool) -> list:
    """
    Runs an episode and returns the transitions that were made during it.

    :param tune: Whether to tune the agent while playing the episode.

    :return: list
    """
    is_done = False
    state, _ = self.env.reset()
    episode_transitions = list()

    while not is_done:
      action = self.select_action(torch.from_numpy(state.astype(np.float32)))
      next_state, reward, is_done, _, _ = self.env.step(action)

      current_transition = Transition(state, action, reward, next_state, is_done)
      self.replay_memory.push(current_transition)
      episode_transitions.append(current_transition)

      if len(self.replay_memory) > self._required_replay_size and tune:
        self.tune()

      state = next_state
      self._anneal_epsilon()

      if self._steps_since_update % self.target_update_steps == 0:
        self._update_target()
      continue

    return episode_transitions