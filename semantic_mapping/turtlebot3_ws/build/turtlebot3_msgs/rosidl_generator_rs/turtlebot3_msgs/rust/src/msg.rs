#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



// Corresponds to turtlebot3_msgs__msg__SensorState
/// CONSTANTS
///
/// Bumper states (states are combined, when multiple bumpers are pressed)

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct SensorState {
    /// Messages
    pub header: std_msgs::msg::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub bumper: u8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub cliff: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub sonar: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub illumination: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub led: u8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub button: u8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub torque: bool,

    /// (-2,147,483,648 ~ 2,147,483,647)
    pub left_encoder: i32,

    /// (-2,147,483,648 ~ 2,147,483,647)
    pub right_encoder: i32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub battery: f32,

}

impl SensorState {

    // This constant is not documented.
    #[allow(missing_docs)]
    pub const BUMPER_FORWARD: u8 = 1;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const BUMPER_BACKWARD: u8 = 2;

    /// Cliff sensor states (states are combined, when multiple cliff sensors are triggered)
    pub const CLIFF: u8 = 1;

    /// Sonar sensor states (states are combined, when multiple sonar sensors are triggered)
    pub const SONAR: u8 = 1;

    /// Illumination sensor (states are combined, when multiple illumination sensors are triggered)
    pub const ILLUMINATION: u8 = 1;

    /// Button states (states are combined, when multiple buttons are pressed)
    pub const BUTTON0: u8 = 1;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const BUTTON1: u8 = 2;

    /// Motor errors
    pub const ERROR_LEFT_MOTOR: u8 = 1;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const ERROR_RIGHT_MOTOR: u8 = 2;

    /// Motor torque
    pub const TORQUE_ON: u8 = 1;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const TORQUE_OFF: u8 = 2;

}


impl Default for SensorState {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::SensorState::default())
  }
}

impl rosidl_runtime_rs::Message for SensorState {
  type RmwMsg = super::msg::rmw::SensorState;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        bumper: msg.bumper,
        cliff: msg.cliff,
        sonar: msg.sonar,
        illumination: msg.illumination,
        led: msg.led,
        button: msg.button,
        torque: msg.torque,
        left_encoder: msg.left_encoder,
        right_encoder: msg.right_encoder,
        battery: msg.battery,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
      bumper: msg.bumper,
      cliff: msg.cliff,
      sonar: msg.sonar,
      illumination: msg.illumination,
      led: msg.led,
      button: msg.button,
      torque: msg.torque,
      left_encoder: msg.left_encoder,
      right_encoder: msg.right_encoder,
      battery: msg.battery,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      bumper: msg.bumper,
      cliff: msg.cliff,
      sonar: msg.sonar,
      illumination: msg.illumination,
      led: msg.led,
      button: msg.button,
      torque: msg.torque,
      left_encoder: msg.left_encoder,
      right_encoder: msg.right_encoder,
      battery: msg.battery,
    }
  }
}


// Corresponds to turtlebot3_msgs__msg__Sound
/// CONSTANTS

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Sound {
    /// Messages
    pub value: u8,

}

impl Sound {

    // This constant is not documented.
    #[allow(missing_docs)]
    pub const OFF: u8 = 0;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const ON: u8 = 1;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const LOW_BATTERY: u8 = 2;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const ERROR: u8 = 3;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const BUTTON1: u8 = 4;


    // This constant is not documented.
    #[allow(missing_docs)]
    pub const BUTTON2: u8 = 5;

}


impl Default for Sound {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::Sound::default())
  }
}

impl rosidl_runtime_rs::Message for Sound {
  type RmwMsg = super::msg::rmw::Sound;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        value: msg.value,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      value: msg.value,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      value: msg.value,
    }
  }
}


// Corresponds to turtlebot3_msgs__msg__VersionInfo
/// Messages

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct VersionInfo {
    /// <yyyy>.<mm>.<dd>        : hardware version of Turtlebot3 (ex. 2017.05.23)
    pub hardware: std::string::String,

    /// <major>.<minor>.<patch> : firmware version of OpenCR
    pub firmware: std::string::String,

    /// <major>.<minor>.<patch> : software version of Turtlebot3 ROS packages
    pub software: std::string::String,

}



impl Default for VersionInfo {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::VersionInfo::default())
  }
}

impl rosidl_runtime_rs::Message for VersionInfo {
  type RmwMsg = super::msg::rmw::VersionInfo;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        hardware: msg.hardware.as_str().into(),
        firmware: msg.firmware.as_str().into(),
        software: msg.software.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        hardware: msg.hardware.as_str().into(),
        firmware: msg.firmware.as_str().into(),
        software: msg.software.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      hardware: msg.hardware.to_string(),
      firmware: msg.firmware.to_string(),
      software: msg.software.to_string(),
    }
  }
}


