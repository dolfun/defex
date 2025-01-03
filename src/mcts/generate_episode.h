#pragma once
#include "mcts_common.h"
#include "mcts.h"
#include <thread>
#include <atomic>
#include <latch>
#include <random>

namespace mcts {

template <StateConcept State, EvaluationQueueConcept<State> EvaluationQueue>
auto generate_episode(
  const State& state, int simulations_per_move, int thread_count, 
  float c_puct, int virtual_loss, EvaluationQueue& evaluation_queue)
    -> std::vector<Evaluation<State>> {

  std::vector<Evaluation<State>> state_evaluations;
  auto node = std::make_shared<Node<State>>();
  node->state = std::make_unique<State>(state);
  while (true) {
    std::atomic<int> simulation_count;
    std::latch latch { thread_count + 1 };
    std::atomic<int> finished_count;
    auto task = [&] {
      latch.arrive_and_wait();
      while (simulation_count < simulations_per_move) {
        bool success = run_mcts_simulation<State>(node, c_puct, virtual_loss, evaluation_queue);
        if (success) ++simulation_count;
      }
      ++finished_count;
    };

    std::vector<std::thread> threads;
    threads.reserve(thread_count);
    for (int i = 0; i < thread_count; ++i) {
      threads.emplace_back(task);
    }

    latch.count_down();
    while (finished_count < thread_count) {
      evaluation_queue.run();
    }

    for (auto& thread : threads) {
      thread.join();
    }

    if (node->children.empty()) break;

    std::vector<float> priors(State::action_count);
    std::vector<int> weights;
    weights.reserve(node->children.size());
    for (auto child : node->children) {
      weights.push_back(child->visit_count);
      priors[child->action_idx] = static_cast<float>(child->visit_count) / (node->visit_count - 1);
    }

    static std::random_device rd{};
    static std::mt19937 engine { rd() };
    std::discrete_distribution<int> dist(weights.begin(), weights.end());
    NodePtr<State> next_node = node->children[dist(engine)];
    int action_idx = next_node->action_idx;

    state_evaluations.emplace_back(*node->state, action_idx, priors);
    next_node->state = std::make_unique<State>(*node->state);
    next_node->state->transition(action_idx);
    node = next_node;
  }

  auto reward = node->state->reward();
  for (auto& evaluation : state_evaluations) {
    evaluation.reward = reward;
  }

  return state_evaluations;
}

};