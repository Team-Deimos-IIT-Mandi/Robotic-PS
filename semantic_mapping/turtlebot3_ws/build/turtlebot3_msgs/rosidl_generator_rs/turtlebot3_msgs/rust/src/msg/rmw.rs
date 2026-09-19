#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};


#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__SensorState() -> *const std::ffi::c_void;
}

#[link(name = "turtlebot3_msgs__rosidl_generator_c")]
extern "C" {
    fn turtlebot3_msgs__msg__SensorState__init(msg: *mut SensorState) -> bool;
    fn turtlebot3_msgs__msg__SensorState__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<SensorState>, size: usize) -> bool;
    fn turtlebot3_msgs__msg__SensorState__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<SensorState>);
    fn turtlebot3_msgs__msg__SensorState__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<SensorState>, out_seq: *mut rosidl_runtime_rs::Sequence<SensorState>) -> bool;
}

// Corresponds to turtlebot3_msgs__msg__SensorState
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]

/// CONSTANTS
///
/// Bumper states (states are combined, when multiple bumpers are pressed)

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct SensorState {
    /// Messages
    pub header: std_msgs::msg::rmw::Header,


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
    unsafe {
      let mut msg = std::mem::zeroed();
      if !turtlebot3_msgs__msg__SensorState__init(&mut msg as *mut _) {
        panic!("Call to turtlebot3_msgs__msg__SensorState__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for SensorState {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__SensorState__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__SensorState__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__SensorState__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for SensorState {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for SensorState where Self: Sized {
  const TYPE_NAME: &'static str = "turtlebot3_msgs/msg/SensorState";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__SensorState() }
  }
}


#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__Sound() -> *const std::ffi::c_void;
}

#[link(name = "turtlebot3_msgs__rosidl_generator_c")]
extern "C" {
    fn turtlebot3_msgs__msg__Sound__init(msg: *mut Sound) -> bool;
    fn turtlebot3_msgs__msg__Sound__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<Sound>, size: usize) -> bool;
    fn turtlebot3_msgs__msg__Sound__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<Sound>);
    fn turtlebot3_msgs__msg__Sound__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<Sound>, out_seq: *mut rosidl_runtime_rs::Sequence<Sound>) -> bool;
}

// Corresponds to turtlebot3_msgs__msg__Sound
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]

/// CONSTANTS

#[repr(C)]
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
    unsafe {
      let mut msg = std::mem::zeroed();
      if !turtlebot3_msgs__msg__Sound__init(&mut msg as *mut _) {
        panic!("Call to turtlebot3_msgs__msg__Sound__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for Sound {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__Sound__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__Sound__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__Sound__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for Sound {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for Sound where Self: Sized {
  const TYPE_NAME: &'static str = "turtlebot3_msgs/msg/Sound";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__Sound() }
  }
}


#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__VersionInfo() -> *const std::ffi::c_void;
}

#[link(name = "turtlebot3_msgs__rosidl_generator_c")]
extern "C" {
    fn turtlebot3_msgs__msg__VersionInfo__init(msg: *mut VersionInfo) -> bool;
    fn turtlebot3_msgs__msg__VersionInfo__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<VersionInfo>, size: usize) -> bool;
    fn turtlebot3_msgs__msg__VersionInfo__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<VersionInfo>);
    fn turtlebot3_msgs__msg__VersionInfo__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<VersionInfo>, out_seq: *mut rosidl_runtime_rs::Sequence<VersionInfo>) -> bool;
}

// Corresponds to turtlebot3_msgs__msg__VersionInfo
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]

/// Messages

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct VersionInfo {
    /// <yyyy>.<mm>.<dd>        : hardware version of Turtlebot3 (ex. 2017.05.23)
    pub hardware: rosidl_runtime_rs::String,

    /// <major>.<minor>.<patch> : firmware version of OpenCR
    pub firmware: rosidl_runtime_rs::String,

    /// <major>.<minor>.<patch> : software version of Turtlebot3 ROS packages
    pub software: rosidl_runtime_rs::String,

}



impl Default for VersionInfo {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !turtlebot3_msgs__msg__VersionInfo__init(&mut msg as *mut _) {
        panic!("Call to turtlebot3_msgs__msg__VersionInfo__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for VersionInfo {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__VersionInfo__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__VersionInfo__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { turtlebot3_msgs__msg__VersionInfo__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for VersionInfo {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for VersionInfo where Self: Sized {
  const TYPE_NAME: &'static str = "turtlebot3_msgs/msg/VersionInfo";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__turtlebot3_msgs__msg__VersionInfo() }
  }
}


