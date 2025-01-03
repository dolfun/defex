from policy_value_network import PolicyValueNetwork
from container_solver import generate_episode

import torch.multiprocessing as mp
from tqdm import tqdm
import tempfile
import pickle
import numpy as np
import torch

def dump_episode(episode, file):
  for evaluation in episode:
    container = evaluation.container
    height_map = np.array(container.height_map, dtype=np.float32) / container.height
    image_data = np.expand_dims(height_map, axis=0)
    additional_data = np.array(container.normalized_packages, dtype=np.float32)
    priors = np.array(evaluation.priors, dtype=np.float32)
    reward = np.array([evaluation.reward], dtype=np.float32)
    pickle.dump((image_data, additional_data, priors, reward), file)

def load_evaluations(file):
  evaluations = []
  file.seek(0)
  while True:
    try:
      evaluations.append(pickle.load(file))
    except EOFError:
      break
  return evaluations

@torch.no_grad()
def evaluate(containers):
  global model, device

  image_data = []
  additional_data = []
  for container in containers:
    height_map = np.array(container.height_map, dtype=np.float32) / container.height
    image_data.append(np.expand_dims(height_map, axis=0))
    additional_data.append(np.array(container.normalized_packages, dtype=np.float32))
  
  image_data = torch.tensor(np.stack(image_data, axis=0), device=device)
  additional_data = torch.tensor(np.stack(additional_data, axis=0), device=device)
  policy, value = model.forward(image_data, additional_data)
  policy = torch.softmax(policy, dim=1)
  result = (policy.cpu().numpy(), value.cpu().numpy())
  return result

def init_worker(_config, model_path, _device):
  global config, model, device

  config = _config
  device = _device

  model = PolicyValueNetwork().to(device)
  model.load_state_dict(torch.load(model_path, weights_only=False))
  model.eval()

def generate_training_data_wrapper(_):
  global config, model, device

  episode = generate_episode(
    config['simulations_per_move'], config['thread_count'],
    config['c_puct'], config['virtual_loss'],
    config['batch_size'], evaluate
  )

  return episode

threshold = None
def generate_training_data(config, model_path, device):
  global threshold
  if threshold is None:
    threshold = config['threshold']

  file = tempfile.TemporaryFile()
  initargs = (config, model_path, device)
  with mp.Pool(config['processes'], initializer=init_worker, initargs=initargs) as p:
    episode_count = config['games_per_iteration']
    args = [None for _ in range(episode_count)]

    it = p.imap_unordered(generate_training_data_wrapper, args)
    for episode in tqdm(it, total=episode_count):
      dump_episode(episode, file)

  evaluations = load_evaluations(file)
  rewards = []
  reshaped_rewards = { +1:0, -1:0 }
  data_points_count = len(evaluations)
  for evaluation in evaluations:
    reward = evaluation[-1][0]
    rewards.append(reward)
    reshaped_reward = +1 if reward > threshold else -1
    reshaped_rewards[reshaped_reward] += 1
    evaluation[-1][0] = reshaped_reward

  rewards = np.array(rewards)
  mean_reward = rewards.mean()
  wins = reshaped_rewards[+1]
  losses = reshaped_rewards[-1]
  win_ratio = wins / (wins + losses)
  print(f'{data_points_count} data points generated!')
  print(f'Average reward: {mean_reward:.2f} ± {rewards.std():.3f}')
  print(f'Threshold: {threshold:.3f}')
  print(f'Reshaped reward: {wins} wins, {losses} losses ({win_ratio * 100:.1f}%)')

  if mean_reward > threshold:
    momentum = config['threshold_momentum']
    threshold = (1 - momentum) * threshold + momentum * mean_reward

  return evaluations