from bin_packing_solver import State
import torch
from torch import nn

class ResidualBlock(nn.Module):
  def __init__(self, nr_channels):
    super(ResidualBlock, self).__init__()
    self.conv1 = nn.Conv2d(nr_channels, nr_channels, kernel_size=3, stride=1, padding=1)
    self.bn1 = nn.BatchNorm2d(nr_channels)
    self.relu = nn.ReLU()
    self.conv2 = nn.Conv2d(nr_channels, nr_channels, kernel_size=3, stride=1, padding=1)
    self.bn2 = nn.BatchNorm2d(nr_channels)

  def forward(self, x):
    residual = x
    out = self.conv1(x)
    out = self.bn1(out)
    out = self.relu(out)
    out = self.conv2(out)
    out = self.bn2(out)
    out += residual
    out = self.relu(out)
    return out

class PolicyValueNetwork(nn.Module):
  def __init__(self, nr_residual_blocks=6):
    super(PolicyValueNetwork, self).__init__()
    base_size = State.bin_length
    in_channels = 2
    additional_input_size = State.item_count * State.values_per_item
    nr_channels = 32

    self.conv_init = nn.Sequential(
      nn.Conv2d(in_channels, nr_channels, kernel_size=3, stride=1, padding=1),
      nn.BatchNorm2d(nr_channels),
      nn.ReLU()
    )

    self.residual_blocks = nn.ModuleList([
      ResidualBlock(nr_channels) for _ in range(nr_residual_blocks)
    ])

    conv_final_nr_channels = 4
    self.conv_final = nn.Sequential(
      nn.Conv2d(nr_channels, conv_final_nr_channels, kernel_size=3, stride=1, padding=1),
      nn.BatchNorm2d(conv_final_nr_channels),
      nn.ReLU()
    )

    fc_additional_output_size = 256
    self.fc_additional = nn.Sequential(
      nn.Linear(additional_input_size, 256),
      nn.ReLU(),
      nn.Linear(256, fc_additional_output_size),
      nn.ReLU()
    )

    base_area = base_size * base_size
    fc_fusion_input_size = conv_final_nr_channels * base_area + fc_additional_output_size
    fc_fusion_output_size = 256
    self.fc_fusion = nn.Sequential(
      nn.Linear(fc_fusion_input_size, 256),
      nn.ReLU(),
      nn.Linear(256, fc_fusion_output_size),
      nn.ReLU()
    )

    self.policy_head = nn.Linear(fc_fusion_output_size, base_area)

    self.value_head = nn.Sequential(
      nn.Linear(fc_fusion_output_size, 256),
      nn.ReLU(),
      nn.Linear(256, 1),
      nn.Sigmoid()
    )

  def forward(self, in_image, in_additional):
    out_image = self.conv_init(in_image)

    for block in self.residual_blocks:
      out_image = block(out_image)

    out_image = self.conv_final(out_image)
    
    out_image = torch.flatten(out_image, start_dim=1)
    out_additional = self.fc_additional(in_additional)
    fused = torch.cat((out_image, out_additional), dim=1)
    fused = self.fc_fusion(fused)

    policy = self.policy_head(fused)
    value = self.value_head(fused)

    return policy, value