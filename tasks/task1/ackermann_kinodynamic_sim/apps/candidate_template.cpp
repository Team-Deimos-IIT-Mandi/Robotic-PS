/**
 * ============================================================================
 * INTER IIT TECH MEET - CANDIDATE STARTER CLIENT TEMPLATE
 * ============================================================================
 * Scenario: Autonomous Ackermann Vehicle Path Planning & Control
 * Objective: Connect to the TCP simulator, query scenario metadata, solve 
 *            path planning/navigation, and stream control commands (v, delta).
 * ============================================================================
 */

#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <cmath>
#include <chrono>
#include <future>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <algorithm>
#include <queue>
#include <unordered_map>
#include <tuple>
#include <limits>
#include <cerrno>

bool readLine(int sock, std::string& pending, std::string& line) {
    while (true) {
        auto end = pending.find('\n');
        if (end != std::string::npos) {
            line = pending.substr(0, end);
            pending.erase(0, end + 1);
            return true;
        }
        char buffer[16384];
        ssize_t n = read(sock, buffer, sizeof(buffer));
        if (n > 0) pending.append(buffer, static_cast<size_t>(n));
        else if (n < 0 && errno == EINTR) continue;
        else return false;
    }
}

bool sendMessage(int sock, const std::string& msg) {
    size_t sent = 0;
    while (sent < msg.size()) {
        ssize_t n = send(sock, msg.data() + sent, msg.size() - sent, MSG_NOSIGNAL);
        if (n > 0) sent += static_cast<size_t>(n);
        else if (n < 0 && errno == EINTR) continue;
        else return false;
    }
    return true;
}
struct VehicleParams {
    double length = 4.0;
    double width = 1.8;
    double wheelbase = 2.5;
    double max_steer = 0.60; // rad
    double max_speed = 2.5;  // m/s
    double min_speed = -1.5; // m/s
};

struct Pose2D {
    double x = 0.0;
    double y = 0.0;
    double yaw = 0.0;
    double v = 0.0;
    double delta = 0.0;
};

enum Direction { FORWARD = 0, REVERSE = 1 };

bool goalRegionHasFreeCell(const std::vector<uint8_t>& grid, int cols, int rows,
                           double res, double ox, double oy,
                           double x, double y, double radius) {
    int cx = static_cast<int>(std::floor((x-ox)/res));
    int cy = static_cast<int>(std::floor((y-oy)/res));
    int extent = static_cast<int>(std::ceil(radius/res)) + 1;
    for (int gy = cy-extent; gy <= cy+extent; ++gy) {
        for (int gx = cx-extent; gx <= cx+extent; ++gx) {
            if (gx < 0 || gy < 0 || gx >= cols || gy >= rows || grid[gy*cols+gx]) continue;
            double px = std::clamp(x, ox+gx*res, ox+(gx+1)*res);
            double py = std::clamp(y, oy+gy*res, oy+(gy+1)*res);
            if (std::hypot(px-x, py-y) < radius) return true;
        }
    }
    return false;
}

struct StateKey {
    int x_bin;
    int y_bin;
    int yaw_bin;
    Direction dir;

    bool operator==(const StateKey& other) const {
        return x_bin == other.x_bin && y_bin == other.y_bin && yaw_bin == other.yaw_bin && dir == other.dir;
    }
};

struct StateKeyHash {
    std::size_t operator()(const StateKey& k) const {
        std::size_t h1 = std::hash<int>()(k.x_bin);
        std::size_t h2 = std::hash<int>()(k.y_bin);
        std::size_t h3 = std::hash<int>()(k.yaw_bin);
        std::size_t h4 = std::hash<int>()(k.dir);
        return h1 ^ (h2 << 1) ^ (h3 << 2) ^ (h4 << 3);
    }
};

struct AStarNode {
    Pose2D state;
    double g_cost;
    double h_cost;
    int parent_index;
    double v_used;
    double delta_used;
    Direction dir;
};

class CandidateSolver {
public:
    CandidateSolver() {}

    /**
     * @param start Initial vehicle pose (x, y, yaw)
     * @param goal Target vehicle pose (x, y, yaw)
     * @param grid 1D vector representing binary occupancy grid (0=Free, 1=Obstacle)
     * @param cols Grid columns count
     * @param rows Grid rows count
     * @param res Grid cell resolution in meters (0.2m)
     * @param params Vehicle physical dimensions and steering limits
     * @return std::vector<Pose2D> Planned trajectory
     */
    std::vector<Pose2D> solve(const Pose2D& start, const Pose2D& goal, 
                              const std::vector<uint8_t>& grid, int cols, int rows, double res,
                              double orig_x, double orig_y,
                              const VehicleParams& params,
                              double goal_position_tolerance = 0.40,
                              bool require_goal_yaw = true) {
        std::cout << "[Candidate Template] Running solver..." << std::endl;
        std::vector<Pose2D> path;

        // 1. Convert a world (x,y) into grid (gx,gy)
        auto worldToGrid = [&](double wx, double wy, int& gx, int& gy) {
            gx = static_cast<int>(std::floor((wx - orig_x) / res));
            gy = static_cast<int>(std::floor((wy - orig_y) / res));
        };

        // 2. Check whether that grid cell is an obstacle
        auto isObstacle = [&](double wx, double wy) -> bool {
            int gx, gy;
            worldToGrid(wx, wy, gx, gy);
            if (gx < 0 || gx >= cols || gy < 0 || gy >= rows) return true; // Treat outside map as obstacle
            return grid[gy * cols + gx] != 0;
        };

        if (!goalRegionHasFreeCell(grid, cols, rows, res, orig_x, orig_y,
                                   goal.x, goal.y, goal_position_tolerance)) {
            std::cerr << "[Planner] Goal region is entirely occupied at ("
                      << goal.x << ", " << goal.y << ")." << std::endl;
            return {};
        }

        // 3. Vehicle Kinematic Propagation
        auto stepVehicle = [&](const Pose2D& state, double v, double delta, double dt) -> Pose2D {
            Pose2D next = state;
            // Respect vehicle speed and steering limits
            double cmd_v = std::max(params.min_speed, std::min(params.max_speed, v));
            double cmd_delta = std::max(-params.max_steer, std::min(params.max_steer, delta));
            // Simulator default: 1 rad/s (not included in CONFIG).
            cmd_delta = state.delta + std::clamp(cmd_delta-state.delta, -dt, dt);
            
            // Apply Ackermann kinematics
            next.x += cmd_v * std::cos(state.yaw) * dt;
            next.y += cmd_v * std::sin(state.yaw) * dt;
            next.yaw += (cmd_v / params.wheelbase) * std::tan(cmd_delta) * dt;
            
            // Normalize yaw to [-pi, pi]
            next.yaw = std::atan2(std::sin(next.yaw), std::cos(next.yaw));
            
            next.v = cmd_v;
            next.delta = cmd_delta;
            return next;
        };

        // 4. Collision checking for a full state
        auto isStateCollision = [&](const Pose2D& state) -> bool {
            const double margin = res;
            double x_rear = -0.8 - margin;
            double x_front = params.wheelbase + 0.7 + margin;
            double y_left = params.width / 2.0 + margin;
            double y_right = -params.width / 2.0 - margin;

            std::vector<std::pair<double, double>> local_points;
            
            // Vehicle center
            local_points.push_back({(x_front + x_rear) / 2.0, 0.0});
            
            double spacing = res / 2.0;

            // Top and bottom edges
            for (double x = x_rear; x <= x_front; x += spacing) {
                local_points.push_back({x, y_left});
                local_points.push_back({x, y_right});
            }
            // Ensure exact corners are checked
            local_points.push_back({x_front, y_left});
            local_points.push_back({x_front, y_right});
            local_points.push_back({x_rear, y_left});
            local_points.push_back({x_rear, y_right});

            // Left and right edges (front and rear bumpers)
            for (double y = y_right; y <= y_left; y += spacing) {
                local_points.push_back({x_front, y});
                local_points.push_back({x_rear, y});
            }

            double cos_yaw = std::cos(state.yaw);
            double sin_yaw = std::sin(state.yaw);

            for (const auto& p : local_points) {
                double xl = p.first;
                double yl = p.second;
                double xw = state.x + xl * cos_yaw - yl * sin_yaw;
                double yw = state.y + xl * sin_yaw + yl * cos_yaw;

                if (isObstacle(xw, yw)) {
                    return true;
                }
            }
            return false;
        };

        // 5. Check if a motion is collision free
        auto isMotionCollisionFree = [&](const Pose2D& state, double v, double delta, double dt, int num_steps) -> bool {
            Pose2D curr = state;
            for (int i = 0; i < num_steps; ++i) {
                curr = stepVehicle(curr, v, delta, dt);
                if (isStateCollision(curr)) {
                    return false;
                }
            }
            return true;
        };

        // --------------------------------------------------------------------
        // HYBRID A* IMPLEMENTATION
        // --------------------------------------------------------------------
        
        auto getYawDiff = [](double yaw1, double yaw2) -> double {
            double diff = yaw1 - yaw2;
            while(diff > M_PI) diff -= 2.0 * M_PI;
            while(diff < -M_PI) diff += 2.0 * M_PI;
            return std::abs(diff);
        };

        auto getKey = [](const Pose2D& state, Direction dir) -> StateKey {
            StateKey k;
            k.x_bin = static_cast<int>(std::floor(state.x / 0.5));
            k.y_bin = static_cast<int>(std::floor(state.y / 0.5));
            double yaw_norm = state.yaw;
            while(yaw_norm < 0) yaw_norm += 2.0 * M_PI;
            while(yaw_norm >= 2.0 * M_PI) yaw_norm -= 2.0 * M_PI;
            k.yaw_bin = static_cast<int>(std::floor(yaw_norm / (15.0 * M_PI / 180.0)));
            k.dir = dir;
            return k;
        };

        auto getHeuristic = [&](const Pose2D& state) -> double {
            double dist = std::hypot(goal.x - state.x, goal.y - state.y);
            double heading_err = require_goal_yaw ? getYawDiff(state.yaw, goal.yaw) : 0.0;
            return dist + 0.1 * heading_err;
        };
        
        auto isGoal = [&](const Pose2D& state) -> bool {
            double dist = std::hypot(goal.x - state.x, goal.y - state.y);
            double heading_err = getYawDiff(state.yaw, goal.yaw);
            return dist < goal_position_tolerance &&
                   (!require_goal_yaw || heading_err < 0.30);
        };

        std::vector<AStarNode> all_nodes;
        std::unordered_map<StateKey, double, StateKeyHash> closed_set;
        
        auto cmp = [&](int a, int b) {
            double fa = all_nodes[a].g_cost + all_nodes[a].h_cost;
            double fb = all_nodes[b].g_cost + all_nodes[b].h_cost;
            return fa > fb; // smallest f first
        };
        std::priority_queue<int, std::vector<int>, decltype(cmp)> open_set(cmp);

        // Constants for penalty weights
        const double W_DIST = 1.0;
        const double W_REVERSE = 2.0;
        const double W_SWITCH = 10.0;
        const double W_STEER_CHANGE = 0.5;

        // Initialize Start Node
        AStarNode start_node;
        start_node.state = start;
        start_node.g_cost = 0.0;
        start_node.h_cost = getHeuristic(start);
        start_node.parent_index = -1;
        start_node.v_used = 0.0;
        start_node.delta_used = 0.0;
        start_node.dir = FORWARD;
        
        all_nodes.push_back(start_node);
        open_set.push(0);
        closed_set[getKey(start, FORWARD)] = 0.0;
        
        // Define motion primitives parameters
        double sim_dt = 0.1;
        int sim_steps = 5;
        double steering_vals[5] = {
            -params.max_steer,
            -0.5 * params.max_steer,
            0.0,
            0.5 * params.max_steer,
            params.max_steer
        };
        double speeds[2] = { params.max_speed, params.min_speed };
        Direction dirs[2] = { FORWARD, REVERSE };

        int goal_node_idx = -1;
        int expanded_nodes = 0;
        
        while (!open_set.empty()) {
            int curr_idx = open_set.top();
            open_set.pop();
            // Successor insertion can reallocate all_nodes; keep a stable copy.
            const AStarNode curr_node = all_nodes[curr_idx];
            
            expanded_nodes++;
            if (expanded_nodes > 250000) {
                std::cerr << "[Planner] Search limit reached; stopping safely." << std::endl;
                return {};
            }
            if (expanded_nodes % 5000 == 0) {
                std::cout << "[Candidate Template] Expanded " << expanded_nodes << " nodes..." << std::endl;
            }

            if (isGoal(curr_node.state)) {
                goal_node_idx = curr_idx;
                break;
            }
            
            for (int d = 0; d < 2; ++d) {
                double v = speeds[d];
                Direction next_dir = dirs[d];
                
                for (int s = 0; s < 5; ++s) {
                    double delta = steering_vals[s];
                    
                    // Simulate motion primitive
                    Pose2D sim_state = curr_node.state;
                    bool collision = false;
                    double dist_travelled = 0.0;
                    
                    for (int step = 0; step < sim_steps; ++step) {
                        Pose2D next_state = stepVehicle(sim_state, v, delta, sim_dt);
                        if (isStateCollision(next_state)) {
                            collision = true;
                            break;
                        }
                        dist_travelled += std::hypot(next_state.x - sim_state.x, next_state.y - sim_state.y);
                        sim_state = next_state;
                    }
                    
                    if (collision) continue;
                    
                    // Calculate costs
                    double g_new = curr_node.g_cost + (dist_travelled * W_DIST);
                    if (next_dir == REVERSE) g_new += (dist_travelled * W_REVERSE);
                    if (next_dir != curr_node.dir) g_new += W_SWITCH;
                    g_new += std::abs(delta - curr_node.delta_used) * W_STEER_CHANGE;
                    
                    StateKey key = getKey(sim_state, next_dir);
                    
                    auto it = closed_set.find(key);
                    if (it == closed_set.end() || g_new < it->second) {
                        closed_set[key] = g_new;
                        
                        AStarNode next_node;
                        next_node.state = sim_state;
                        next_node.g_cost = g_new;
                        next_node.h_cost = getHeuristic(sim_state);
                        next_node.parent_index = curr_idx;
                        next_node.v_used = v;
                        next_node.delta_used = delta;
                        next_node.dir = next_dir;
                        
                        // Pass along the applied motion controls safely to state 
                        next_node.state.v = v;
                        // Keep actual rate-limited steering in the state.
                        
                        all_nodes.push_back(next_node);
                        open_set.push(all_nodes.size() - 1);
                    }
                }
            }
        }
        
        if (goal_node_idx != -1) {
            std::cout << "[Candidate Template] Path found! Nodes expanded: " << expanded_nodes << std::endl;
            int curr = goal_node_idx;
            std::vector<int> chain;
            while(curr != -1) {
                path.push_back(all_nodes[curr].state);
                chain.push_back(curr);
                curr = all_nodes[curr].parent_index;
            }
            std::reverse(path.begin(), path.end());
            std::reverse(chain.begin(), chain.end());
            // Reconstruct the same intermediate states checked by the search.
            std::vector<Pose2D> dense;
            dense.push_back(path.front());
            for (size_t i = 1; i < path.size(); ++i) {
                Pose2D state = dense.back();
                for (int j = 0; j < sim_steps; ++j) {
                    state = stepVehicle(state, all_nodes[chain[i]].v_used,
                                        all_nodes[chain[i]].delta_used, sim_dt);
                    dense.push_back(state);
                }
            }
            path = std::move(dense);
        } else {
            std::cout << "[Candidate Template] Hybrid A* failed to find a path! Expanded: " << expanded_nodes << std::endl;
        }

        return path;
    }
};

int main(int argc, char** argv) {
    std::string ip = "127.0.0.1";
    int port = 8091;

    if (argc > 1) ip = argv[1];
    if (argc > 2) port = std::atoi(argv[2]);

    std::cout << "==========================================================" << std::endl;
    std::cout << "      Inter IIT Tech Meet: Candidate Client Template     " << std::endl;
    std::cout << "==========================================================" << std::endl;

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in serv_addr{};
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(port);
    inet_pton(AF_INET, ip.c_str(), &serv_addr.sin_addr);

    if (connect(sock, reinterpret_cast<sockaddr*>(&serv_addr), sizeof(serv_addr)) < 0) {
        std::cerr << "[Client] Connection failed. Is simulator_node running on port " << port << "?" << std::endl;
        return 1;
    }

    std::cout << "[Client] Connected to simulator server!" << std::endl;

    // Send query
    std::string query = "Q\n";
    if (!sendMessage(sock, query)) { close(sock); return 1; }

    Pose2D start, goal;
    VehicleParams v_params;
    double map_w = 0, map_h = 0, res = 0, orig_x = 0, orig_y = 0;
    int cols = 0, rows = 0;
    std::vector<uint8_t> grid;
    std::vector<Pose2D> waypoints;

    std::string pending;
    std::string line;
    bool got_config = false, got_waypoints = false, got_grid = false;
    while (!got_config || !got_waypoints || !got_grid) {
        if (!readLine(sock, pending, line)) {
            std::cerr << "[Client] Disconnected before complete CONFIG/WAYPOINTS/GRID." << std::endl;
            close(sock); return 1;
        }
        if (line.rfind("CONFIG ", 0) == 0) {
            std::istringstream line_ss(line.substr(7));
            line_ss >> start.x >> start.y >> start.yaw
                    >> goal.x >> goal.y >> goal.yaw
                    >> v_params.length >> v_params.width >> v_params.wheelbase
                    >> v_params.max_steer >> v_params.max_speed >> v_params.min_speed
                    >> map_w >> map_h >> res >> orig_x >> orig_y
                    >> cols >> rows;
            if (!line_ss || cols <= 0 || rows <= 0 || !(res > 0)) {
                std::cerr << "[Client] Invalid CONFIG." << std::endl;
                close(sock); return 1;
            }
            got_config = true;
        }
        else if (line.rfind("WAYPOINTS ", 0) == 0) {
            std::istringstream line_ss(line.substr(10));
            size_t count = 0;
            if (!(line_ss >> count)) {
                std::cerr << "[Client] Invalid WAYPOINTS header." << std::endl;
                close(sock); return 1;
            }
            waypoints.clear();
            waypoints.reserve(count);
            for (size_t i = 0; i < count; ++i) {
                Pose2D waypoint;
                if (!(line_ss >> waypoint.x >> waypoint.y)) {
                    std::cerr << "[Client] Incomplete WAYPOINTS message." << std::endl;
                    close(sock); return 1;
                }
                waypoints.push_back(waypoint);
            }
            std::string extra;
            if (line_ss >> extra) {
                std::cerr << "[Client] Unexpected data in WAYPOINTS message." << std::endl;
                close(sock); return 1;
            }
            got_waypoints = true;
        }
        else if (line.rfind("GRID ", 0) == 0) {
            std::istringstream line_ss(line.substr(5));
            size_t count = 0;
            if (!(line_ss >> count)) { close(sock); return 1; }
            grid.clear();
            int val;
            while (line_ss >> val) grid.push_back(val ? 1 : 0);
            if (grid.size() != count || !line_ss.eof()) {
                std::cerr << "[Client] Invalid GRID cell count/data." << std::endl;
                close(sock); return 1;
            }
            got_grid = true;
        }
    }
    if (grid.size() != static_cast<size_t>(cols) * rows) {
        std::cerr << "[Client] GRID/CONFIG dimensions disagree." << std::endl;
        close(sock); return 1;
    }

    std::cout << "[Client] Config loaded. Map: " << cols << "x" << rows << " resolution: " << res << "m" << std::endl;
    std::cout << "[Client] Navigation targets: "
              << (waypoints.empty() ? 1 : waypoints.size()) << std::endl;

    CandidateSolver solver;
    std::vector<Pose2D> navigation_goals = waypoints;
    if (navigation_goals.empty()) {
        navigation_goals.push_back(goal);
    } else if (std::hypot(navigation_goals.back().x-goal.x,
                          navigation_goals.back().y-goal.y) < 1e-6) {
        navigation_goals.back() = goal;
    } else {
        navigation_goals.push_back(goal);
    }
    size_t active_goal_idx = 0;
    constexpr double INTERMEDIATE_GOAL_TOLERANCE = 0.80;

    auto isFinalGoal = [&]() {
        return active_goal_idx + 1 == navigation_goals.size();
    };
    auto planToActiveGoal = [&](const Pose2D& plan_start) {
        const Pose2D plan_goal = navigation_goals[active_goal_idx];
        const bool final = isFinalGoal();
        return std::async(std::launch::async, [&, plan_start, plan_goal, final]() {
            return solver.solve(plan_start, plan_goal,
                            grid, cols, rows, res, orig_x, orig_y, v_params,
                            final ? 0.40 : INTERMEDIATE_GOAL_TOLERANCE, final);
        });
    };

    std::vector<Pose2D> path;
    std::future<std::vector<Pose2D>> planning;
    enum class Mode { STOPPING, PLANNING, TRACKING, WAIT_SKIP };
    Mode mode = Mode::STOPPING;
    size_t skipped_waypoints = 0;
    if (!sendMessage(sock, "CTRL 0 0\n")) { close(sock); return 1; }
    auto uploadPath = [&]() {
        std::ostringstream msg;
        msg << "TRAJ ";
        for (const auto& p : path) msg << p.x << ' ' << p.y << ' ' << p.yaw << ' ' << p.v << ';';
        msg << '\n';
        std::cout << "[Client] Uploading " << path.size() << " trajectory samples; endpoint=("
                  << path.back().x << ", " << path.back().y << ")." << std::endl;
        return sendMessage(sock, msg.str());
    };
    auto computeControl = [&](const Pose2D& current, const Pose2D& active_goal,
                              bool final_goal, const std::vector<Pose2D>& path,
                              size_t& nearest_idx, double& out_e_y,
                              double& out_e_theta) -> std::pair<double, double> {
        if (path.empty()) {
            out_e_y = 0.0;
            out_e_theta = 0.0;
            return {0.0, 0.0};
        }
        
        auto getYawDiffSigned = [](double target_yaw, double current_yaw) -> double {
            double diff = target_yaw - current_yaw;
            while(diff > M_PI) diff -= 2.0 * M_PI;
            while(diff < -M_PI) diff += 2.0 * M_PI;
            return diff;
        };

        // 2. Find nearest path point
        double min_dist = std::numeric_limits<double>::max();
        size_t best_idx = nearest_idx;
        for (size_t i = nearest_idx; i < path.size(); ++i) {
            double dist = std::hypot(current.x - path[i].x, current.y - path[i].y);
            if (dist < min_dist) {
                min_dist = dist;
                best_idx = i;
            }
        }
        nearest_idx = best_idx;

        // 3. Choose lookahead point
        double lookahead_dist = 1.5; 
        size_t lookahead_idx = nearest_idx;
        double accum_dist = 0.0;
        for (size_t i = nearest_idx; i < path.size() - 1; ++i) {
            accum_dist += std::hypot(path[i+1].x - path[i].x, path[i+1].y - path[i].y);
            lookahead_idx = i + 1;
            if (accum_dist >= lookahead_dist) {
                break;
            }
        }
        // 5. Calculate lateral error (Cross Track Error)
        const Pose2D& reference = path[nearest_idx];
        double dx = current.x - reference.x;
        double dy = current.y - reference.y;
        double path_cos = std::cos(reference.yaw);
        double path_sin = std::sin(reference.yaw);
        double e_y = path_cos * dy - path_sin * dx;

        // 4. Calculate heading error
        double e_theta = getYawDiffSigned(reference.yaw, current.yaw);

        // 7. Handle forward versus reverse
        bool is_reverse = (path[nearest_idx].v < 0);
        if (is_reverse) {
            e_theta = getYawDiffSigned(current.yaw, reference.yaw);
        }

        // 6. Compute steering
        double K_CTE = 0.5;
        double K_YAW = 1.0;
        double delta = path[std::min(nearest_idx+1, path.size()-1)].delta
                       - K_CTE * e_y + K_YAW * e_theta;
        delta = std::max(-v_params.max_steer, std::min(v_params.max_steer, delta));

        // 8. Slow down during difficult tracking
        double target_v = is_reverse ? v_params.min_speed : v_params.max_speed;
        
        // Scan ahead for gear changes
        bool gear_change_upcoming = false;
        size_t scan_idx = nearest_idx;
        double scan_dist = 0.0;
        while (scan_idx < path.size() - 1 && scan_dist < 1.5) {
            scan_dist += std::hypot(path[scan_idx+1].x - path[scan_idx].x, path[scan_idx+1].y - path[scan_idx].y);
            if ((path[scan_idx].v < 0) != is_reverse) {
                gear_change_upcoming = true;
                break;
            }
            scan_idx++;
        }

        if (gear_change_upcoming) {
            target_v *= 0.25; // Reduce speed significantly near direction change
        } else if (std::abs(delta) > 0.4 || std::abs(e_y) > 1.0) {
            target_v *= 0.5; // Slow down for tight turns or large errors
        }

        if (lookahead_idx == path.size() - 1 && min_dist < 2.0) {
            target_v *= 0.5; // Slow down near goal
        }
        if (final_goal &&
            std::hypot(current.x-active_goal.x, current.y-active_goal.y) < 0.40 &&
            std::abs(getYawDiffSigned(active_goal.yaw, current.yaw)) < 0.30) {
            target_v = 0;
            delta = 0;
        }
        
        out_e_y = e_y;
        out_e_theta = e_theta;
        return {target_v, delta};
    };

    size_t target_idx = 0;
    
    // Replanning parameters
    const double REPLAN_CTE_THRESHOLD = 1.0; // 1.0m
    const double REPLAN_YAW_THRESHOLD = 0.5; // rad
    double last_replan_time = -10000.0;
    const double REPLAN_COOLDOWN_MS = 2000.0; // 2 seconds
    bool reached_goal = false;
    size_t replan_count = 0;
    double max_cte = 0.0;
    double first_telemetry_ms = -1.0;

    while (true) {
        if (!readLine(sock, pending, line)) break;
        if (line.rfind("WAYPOINT_SKIPPED ", 0) == 0) {
            std::istringstream reply(line.substr(17));
            size_t index = 0;
            if (mode != Mode::WAIT_SKIP || !(reply >> index) || index != active_goal_idx+1) {
                std::cerr << "[Client] Unexpected skip acknowledgement; stopping." << std::endl;
                break;
            }
            ++skipped_waypoints;
            ++active_goal_idx;
            std::cout << "[Client] Waypoint " << index
                      << " SKIPPED (blocked acceptance area, not reached). Continuing to target "
                      << active_goal_idx+1 << "." << std::endl;
            mode = Mode::STOPPING;
            continue;
        }
        if (line.rfind("WAYPOINT_SKIP_REJECTED ", 0) == 0) {
            std::cerr << "[Client] Simulator rejected waypoint cancellation; stopping." << std::endl;
            break;
        }
        if (line.rfind("TELEMETRY ", 0) == 0) {
            std::istringstream t_ss(line);
            std::string tag;
            uint64_t step;
            double t_ms, cur_x, cur_y, cur_yaw, cur_v, cur_delta;
            int coll, goal_done;
            t_ss >> tag >> step >> t_ms >> cur_x >> cur_y >> cur_yaw >> cur_v >> cur_delta >> coll >> goal_done;
            if (!t_ss) { std::cerr << "[Client] Invalid telemetry." << std::endl; break; }
            if (coll) { std::cout << "[Client] Collision detected!" << std::endl; break; }
            if (first_telemetry_ms < 0) first_telemetry_ms = t_ms;
            if (goal_done) {
                reached_goal = true;
                std::cout << "[Client] Goal reached! Skipped waypoints=" << skipped_waypoints
                          << "; final position error=" << std::hypot(cur_x-goal.x, cur_y-goal.y)
                          << "m; yaw error=" << std::abs(std::atan2(std::sin(cur_yaw-goal.yaw),
                                                                     std::cos(cur_yaw-goal.yaw)))
                          << "rad; speed=" << cur_v << "m/s; elapsed="
                          << (t_ms-first_telemetry_ms)/1000.0 << "s; replans=" << replan_count
                          << "; max CTE=" << max_cte << "m." << std::endl;
                break;
            }

            Pose2D current_state;
            current_state.x = cur_x;
            current_state.y = cur_y;
            current_state.yaw = cur_yaw;
            current_state.v = cur_v;
            current_state.delta = cur_delta;

            if (mode == Mode::WAIT_SKIP) {
                if (!sendMessage(sock, "CTRL 0 0\n")) break;
                continue;
            }
            if (mode == Mode::STOPPING) {
                if (!sendMessage(sock, "CTRL 0 0\n")) break;
                if (std::abs(cur_v) < 0.01 && std::abs(cur_delta) < 0.01) {
                    const auto& target = navigation_goals[active_goal_idx];
                    if (!isFinalGoal() && !goalRegionHasFreeCell(grid, cols, rows, res,
                            orig_x, orig_y, target.x, target.y, 1.2)) {
                        std::cout << "[Client] Target " << active_goal_idx+1
                                  << " acceptance area is blocked; requesting cancellation." << std::endl;
                        if (!sendMessage(sock, "SKIP_WAYPOINT " +
                                              std::to_string(active_goal_idx+1) + "\n")) break;
                        mode = Mode::WAIT_SKIP;
                        continue;
                    }
                    planning = planToActiveGoal(current_state);
                    mode = Mode::PLANNING;
                }
                continue;
            }
            if (mode == Mode::PLANNING) {
                if (!sendMessage(sock, "CTRL 0 0\n")) break;
                if (planning.wait_for(std::chrono::milliseconds(0)) != std::future_status::ready)
                    continue;
                path = planning.get();
                if (path.empty()) {
                    std::cerr << "[Client] No safe path to target " << active_goal_idx+1
                              << "; vehicle remains stopped." << std::endl;
                    break;
                }
                target_idx = 0;
                if (!uploadPath()) break;
                mode = Mode::TRACKING;
            }

            const Pose2D& active_goal = navigation_goals[active_goal_idx];
            if (!isFinalGoal() &&
                std::hypot(cur_x - active_goal.x, cur_y - active_goal.y) <
                    INTERMEDIATE_GOAL_TOLERANCE) {
                if (!sendMessage(sock, "CTRL 0 0\n")) break;
                ++active_goal_idx;
                std::cout << "[Client] Intermediate waypoint " << active_goal_idx
                          << " reached. Planning target " << (active_goal_idx + 1)
                          << "/" << navigation_goals.size() << "." << std::endl;
                mode = Mode::STOPPING;
                continue;
            }
            
            double cur_e_y = 0.0;
            double cur_e_theta = 0.0;
            auto [target_v, target_delta] =
                computeControl(current_state, navigation_goals[active_goal_idx],
                               isFinalGoal(), path, target_idx,
                               cur_e_y, cur_e_theta);
            max_cte = std::max(max_cte, std::abs(cur_e_y));
            // Replanning check
            if ((std::abs(cur_e_y) > REPLAN_CTE_THRESHOLD || std::abs(cur_e_theta) > REPLAN_YAW_THRESHOLD) 
                && (t_ms - last_replan_time > REPLAN_COOLDOWN_MS)) {
                
                std::cout << "[Client] Tracking error too large (e_y=" << cur_e_y << ", e_th=" << cur_e_theta << "). Replanning!" << std::endl;
                if (!sendMessage(sock, "CTRL 0 0\n")) break;
                
                last_replan_time = t_ms;
                ++replan_count;
                mode = Mode::STOPPING;
                continue;
            }

            std::ostringstream cmd_ss;
            cmd_ss << "CTRL " << target_v << " " << target_delta << "\n";
            std::string cmd_str = cmd_ss.str();
            if (!sendMessage(sock, cmd_str)) break;
        }
    }

    sendMessage(sock, "CTRL 0 0\n");
    close(sock);
    return reached_goal ? 0 : 1;
}
