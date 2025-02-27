#pragma once
#include <vector>
#include "state.h"

namespace mcts {

struct Evaluation {
  Evaluation (const State& _state, int _action_idx = -1, const std::vector<float>& _priors = {}, float _value = {})
    : state { _state }, action_idx { _action_idx }, priors { _priors }, value { _value } {}

  State state;
  int action_idx;
  std::vector<float> priors;
  float value;
};

}