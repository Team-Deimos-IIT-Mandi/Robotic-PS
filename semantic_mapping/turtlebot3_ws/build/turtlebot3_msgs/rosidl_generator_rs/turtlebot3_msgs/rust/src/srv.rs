#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};




// Corresponds to turtlebot3_msgs__srv__Sound_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Sound_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub value: u8,

}



impl Default for Sound_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Sound_Request::default())
  }
}

impl rosidl_runtime_rs::Message for Sound_Request {
  type RmwMsg = super::srv::rmw::Sound_Request;

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


// Corresponds to turtlebot3_msgs__srv__Sound_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Sound_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub message: std::string::String,

}



impl Default for Sound_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Sound_Response::default())
  }
}

impl rosidl_runtime_rs::Message for Sound_Response {
  type RmwMsg = super::srv::rmw::Sound_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        success: msg.success,
        message: msg.message.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      success: msg.success,
        message: msg.message.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      success: msg.success,
      message: msg.message.to_string(),
    }
  }
}


// Corresponds to turtlebot3_msgs__srv__Dqn_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Dqn_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub action: u8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub init: bool,

}



impl Default for Dqn_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Dqn_Request::default())
  }
}

impl rosidl_runtime_rs::Message for Dqn_Request {
  type RmwMsg = super::srv::rmw::Dqn_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        action: msg.action,
        init: msg.init,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      action: msg.action,
      init: msg.init,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      action: msg.action,
      init: msg.init,
    }
  }
}


// Corresponds to turtlebot3_msgs__srv__Dqn_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Dqn_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub state: Vec<f32>,


    // This member is not documented.
    #[allow(missing_docs)]
    pub reward: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub done: bool,

}



impl Default for Dqn_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Dqn_Response::default())
  }
}

impl rosidl_runtime_rs::Message for Dqn_Response {
  type RmwMsg = super::srv::rmw::Dqn_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        state: msg.state.into(),
        reward: msg.reward,
        done: msg.done,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        state: msg.state.as_slice().into(),
      reward: msg.reward,
      done: msg.done,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      state: msg.state
          .into_iter()
          .collect(),
      reward: msg.reward,
      done: msg.done,
    }
  }
}


// Corresponds to turtlebot3_msgs__srv__Goal_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Goal_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub structure_needs_at_least_one_member: u8,

}



impl Default for Goal_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Goal_Request::default())
  }
}

impl rosidl_runtime_rs::Message for Goal_Request {
  type RmwMsg = super::srv::rmw::Goal_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        structure_needs_at_least_one_member: msg.structure_needs_at_least_one_member,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      structure_needs_at_least_one_member: msg.structure_needs_at_least_one_member,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      structure_needs_at_least_one_member: msg.structure_needs_at_least_one_member,
    }
  }
}


// Corresponds to turtlebot3_msgs__srv__Goal_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct Goal_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub pose_x: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub pose_y: f32,


    // This member is not documented.
    #[allow(missing_docs)]
    pub success: bool,

}



impl Default for Goal_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::Goal_Response::default())
  }
}

impl rosidl_runtime_rs::Message for Goal_Response {
  type RmwMsg = super::srv::rmw::Goal_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        pose_x: msg.pose_x,
        pose_y: msg.pose_y,
        success: msg.success,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      pose_x: msg.pose_x,
      pose_y: msg.pose_y,
      success: msg.success,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      pose_x: msg.pose_x,
      pose_y: msg.pose_y,
      success: msg.success,
    }
  }
}






#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Sound() -> *const std::ffi::c_void;
}

// Corresponds to turtlebot3_msgs__srv__Sound
#[allow(missing_docs, non_camel_case_types)]
pub struct Sound;

impl rosidl_runtime_rs::Service for Sound {
    type Request = Sound_Request;
    type Response = Sound_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Sound() }
    }
}




#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Dqn() -> *const std::ffi::c_void;
}

// Corresponds to turtlebot3_msgs__srv__Dqn
#[allow(missing_docs, non_camel_case_types)]
pub struct Dqn;

impl rosidl_runtime_rs::Service for Dqn {
    type Request = Dqn_Request;
    type Response = Dqn_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Dqn() }
    }
}




#[link(name = "turtlebot3_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Goal() -> *const std::ffi::c_void;
}

// Corresponds to turtlebot3_msgs__srv__Goal
#[allow(missing_docs, non_camel_case_types)]
pub struct Goal;

impl rosidl_runtime_rs::Service for Goal {
    type Request = Goal_Request;
    type Response = Goal_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__turtlebot3_msgs__srv__Goal() }
    }
}


