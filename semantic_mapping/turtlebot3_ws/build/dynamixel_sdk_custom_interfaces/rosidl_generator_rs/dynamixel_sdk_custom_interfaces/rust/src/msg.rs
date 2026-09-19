#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



// Corresponds to dynamixel_sdk_custom_interfaces__msg__SetPosition
/// Messages

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct SetPosition {

    // This member is not documented.
    #[allow(missing_docs)]
    pub id: u8,


    // This member is not documented.
    #[allow(missing_docs)]
    pub position: i32,

}



impl Default for SetPosition {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::SetPosition::default())
  }
}

impl rosidl_runtime_rs::Message for SetPosition {
  type RmwMsg = super::msg::rmw::SetPosition;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        id: msg.id,
        position: msg.position,
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      id: msg.id,
      position: msg.position,
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      id: msg.id,
      position: msg.position,
    }
  }
}


