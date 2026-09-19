#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};




// Corresponds to dynamixel_sdk_custom_interfaces__srv__GetPosition_Request

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct GetPosition_Request {

    // This member is not documented.
    #[allow(missing_docs)]
    pub id: u8,

}



impl Default for GetPosition_Request {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::GetPosition_Request::default())
  }
}

impl rosidl_runtime_rs::Message for GetPosition_Request {
  type RmwMsg = super::srv::rmw::GetPosition_Request;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        id: msg.id,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      id: msg.id,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      id: msg.id,
    }
  }
}


// Corresponds to dynamixel_sdk_custom_interfaces__srv__GetPosition_Response

// This struct is not documented.
#[allow(missing_docs)]

#[allow(non_camel_case_types)]
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct GetPosition_Response {

    // This member is not documented.
    #[allow(missing_docs)]
    pub position: i32,

}



impl Default for GetPosition_Response {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::srv::rmw::GetPosition_Response::default())
  }
}

impl rosidl_runtime_rs::Message for GetPosition_Response {
  type RmwMsg = super::srv::rmw::GetPosition_Response;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        position: msg.position,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      position: msg.position,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      position: msg.position,
    }
  }
}






#[link(name = "dynamixel_sdk_custom_interfaces__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_service_type_support_handle__dynamixel_sdk_custom_interfaces__srv__GetPosition() -> *const std::ffi::c_void;
}

// Corresponds to dynamixel_sdk_custom_interfaces__srv__GetPosition
#[allow(missing_docs, non_camel_case_types)]
pub struct GetPosition;

impl rosidl_runtime_rs::Service for GetPosition {
    type Request = GetPosition_Request;
    type Response = GetPosition_Response;

    fn get_type_support() -> *const std::ffi::c_void {
        // SAFETY: No preconditions for this function.
        unsafe { rosidl_typesupport_c__get_service_type_support_handle__dynamixel_sdk_custom_interfaces__srv__GetPosition() }
    }
}


