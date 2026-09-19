#include <iostream>
#include <cstdlib>
#include <chrono>
#include <thread>
#include <cmath>
#include "simulator.hpp"

using namespace ackermann_sim;

int main(int argc, char** argv) {
    uint16_t port = 8091;
    ScenarioType scenario = ScenarioType::PARALLEL_PARKING_STREET;
    double time_scale = 5.0;

    if (argc > 1) {
        port = static_cast<uint16_t>(std::atoi(argv[1]));
    }
    if (argc > 2) {
        int sc_id = std::atoi(argv[2]);
        if (sc_id == 1) scenario = ScenarioType::PARALLEL_PARKING_LOT;
        else if (sc_id == 2) scenario = ScenarioType::SLALOM_COURSE;
        else if (sc_id == 3) scenario = ScenarioType::MULTI_GOAL_WAYPOINTS;
    }
    if (argc > 3) {
        char* end = nullptr;
        time_scale = std::strtod(argv[3], &end);
        if (end == argv[3] || *end != '\0' || !std::isfinite(time_scale) ||
            time_scale <= 0.0 || time_scale > 20.0) {
            std::cerr << "Time scale must be a number in (0, 20]." << std::endl;
            return 1;
        }
    }

    std::cout << "==========================================================" << std::endl;
    std::cout << " INTER IIT TECH MEET: Autonomous Kinodynamic Simulator   " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << " Listening Port: " << port << std::endl;
    std::cout << " Usage: ./simulator_node [port] [scenario_id] [time_scale=5]" << std::endl;
    std::cout << " Time scale: " << time_scale << " simulated seconds per real second" << std::endl;
    std::cout << "        Scenario 0: Street Parallel Parking" << std::endl;
    std::cout << "        Scenario 1: Parking Lot Bay" << std::endl;
    std::cout << "        Scenario 2: Slalom Track" << std::endl;
    std::cout << "        Scenario 3: Multi-Goal Navigation" << std::endl;
    std::cout << " Press ESC or 'q' in visualizer to exit." << std::endl;
    std::cout << " Manual teleop: W (forward), S (reverse), A (steer left), D (steer right), Space (brake)" << std::endl;
    std::cout << "==========================================================" << std::endl;

    GameWorld gameWorld(port, scenario);

    const auto wall_step = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
        std::chrono::duration<double>(gameWorld.getTimeStep() / time_scale));
    auto next_tick = std::chrono::steady_clock::now();
    while (gameWorld.spinOnce()) {
        next_tick += wall_step;
        std::this_thread::sleep_until(next_tick);
    }

    std::cout << "[Simulator] Exiting simulation." << std::endl;
    return 0;
}
