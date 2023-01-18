import numpy as np
import torch
from .dqn_base import DQNBase


class DoubleDQN(DQNBase):

  def compute_loss(self) -> float:
    """
    Compute the loss for a Double DQN implementation.

    Based on the Double DQN paper "Deep Reinforcement Learning with Double Q-Learning" (Hasselt et al., 2015)

    DQN Bellman Update:
      >> state = experience_replay.state
      >> next_state = experience_replay.next_state

      >> state_max_q = argmax(online_network.predict(state))
      >> next_state_max_q = argmax(target_network.predict(next_state))

      >>expected_q = reward + discount_factor * next_state_max_q
      >>loss = LossFunction(predicted_q, expected_q)

    DDQN Bellman Update:
      >> state = experience_replay.state
      >> next_state = experience_replay.next_state

      >> state_max_q = argmax(online_network.predict(state))
      >> next_state_q_values = target_network.predict(next_state)

      >> next_state_action = argmax(online_network.predict(next_state))
      >> next_state_action_value = next_state_q_values.where(action = next_action)
      >> expected_q = reward + discount_factor * next_state_action_value

      >> loss = LossFunction(predicted_q, expected_q)

    :return: float
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

    q_values_next = self.predict_q_target(next_states)
    q_values_expected = self.predict_q(states)
    q_values_expected[range(len(q_values_expected)), actions] = rewards + self.discount_rate * torch.max(q_values_next, axis=1).values
    q_values_expected[is_final_indices.tolist(), actions_tensor[is_final_indices].tolist()] = rewards[is_final_indices.tolist()]

    return self.criterion(self.policy(states), q_values_expected)
