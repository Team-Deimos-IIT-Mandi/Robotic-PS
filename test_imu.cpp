#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>

struct ImuData { float accel_x, accel_y, yaw; };

int main() {
    std::string m_rx_buf = "$ROVER,IMU,0.2,-0.1,1.57*";
    
    // Compute CRC for "ROVER,IMU,0.2,-0.1,1.57"
    std::string body = "ROVER,IMU,0.2,-0.1,1.57";
    uint8_t crc = 0;
    for (char c : body) crc ^= static_cast<uint8_t>(c);
    
    std::ostringstream crc_stream;
    crc_stream << std::uppercase << std::setfill('0') << std::setw(2) << std::hex << static_cast<int>(crc);
    std::string expected_crc = crc_stream.str();
    
    m_rx_buf += expected_crc + "\n";
    std::cout << "Testing string: " << m_rx_buf;

    bool found_valid = false;
    ImuData imu;

    size_t newline_pos;
    while ((newline_pos = m_rx_buf.find('\n')) != std::string::npos) {
        std::string line = m_rx_buf.substr(0, newline_pos);
        m_rx_buf.erase(0, newline_pos + 1);

        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] != '$') continue;

        size_t star_pos = line.find('*');
        if (star_pos == std::string::npos) continue;

        std::string extracted_body = line.substr(1, star_pos - 1);
        std::string provided_crc = line.substr(star_pos + 1);
        
        uint8_t calc_crc = 0;
        for (char c : extracted_body) calc_crc ^= static_cast<uint8_t>(c);
        
        std::ostringstream calc_crc_stream;
        calc_crc_stream << std::uppercase << std::setfill('0') << std::setw(2) << std::hex << static_cast<int>(calc_crc);
        
        if (provided_crc != calc_crc_stream.str()) continue;

        std::istringstream ss(extracted_body);
        std::string token;
        std::vector<std::string> tokens;
        while (std::getline(ss, token, ',')) tokens.push_back(token);

        if (tokens.size() < 5 || tokens[0] != "ROVER" || tokens[1] != "IMU") continue;

        try {
            imu.accel_x = std::stof(tokens[2]);
            imu.accel_y = std::stof(tokens[3]);
            imu.yaw     = std::stof(tokens[4]);
            found_valid = true;
        } catch (...) {
            continue;
        }
    }

    if (found_valid) {
        std::cout << "IMU parsed! accel_x: " << imu.accel_x << " accel_y: " << imu.accel_y << " yaw: " << imu.yaw << std::endl;
    } else {
        std::cout << "Failed to parse IMU!" << std::endl;
    }

    return 0;
}
