#pragma once
#include <memory>
#include <future>
#include <vector>
#include <utility>

namespace mcts {

template <typename State>
concept StateConcept = requires(State& state, int action_idx) {
  { State::action_count } -> std::convertible_to<size_t>;
  { std::as_const(state).possible_actions() } -> std::same_as<std::vector<int>>;
  { state.transition(action_idx) } -> std::same_as<void>;
  { std::as_const(state).reward() } -> std::same_as<float>;
};

template <typename EvaluationQueue, typename State>
concept EvaluationQueueConcept = requires(std::shared_ptr<State> state, EvaluationQueue& evaluation_queue) {
  { evaluation_queue.enqueue(state) } -> std::same_as<std::future<std::pair<std::vector<float>, float>>>;
};

template <typename State>
struct Evaluation {
  Evaluation (const State& _state, int _action_idx = -1, const std::vector<float>& _priors = {}, float _reward = {})
    : state { _state }, action_idx { _action_idx }, priors { _priors }, reward { _reward } {}

  State state;
  int action_idx;
  std::vector<float> priors;
  float reward;
};

}