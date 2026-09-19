/*
   PS7 - Reliable Hardware Discovery
   Arduino Uno / Nano test version

   Serial communication:
   Arduino <---- USB Serial ----> Laptop / Raspberry Pi

   Commands:

   IDENTIFY 1
   ARM SESSION_ID
   HB SESSION_ID
   CMD SESSION_ID SEQUENCE VALUE
   DISARM SESSION_ID

   Safety:
   - Starts stopped
   - Commands rejected before ARM
   - Commands require correct session
   - Duplicate/stale commands rejected
   - Host heartbeat timeout -> SAFE_STOP
*/

#define DEVICE_ID "ARDUINO_LEFT_01"
#define CONTROLLER_ROLE "LEFT_MOTOR"

#define FIRMWARE_VERSION "1.0.0"
#define PROTOCOL_VERSION 1

// Host must send heartbeat at least once per second
const unsigned long HOST_HEARTBEAT_TIMEOUT = 1000;

// Arduino sends heartbeat every 250 ms
const unsigned long ARDUINO_HEARTBEAT_PERIOD = 250;

// Built-in LED is our demo actuator
const int ACTUATOR_PIN = LED_BUILTIN;


// ============================================================
// GLOBAL VARIABLES
// ============================================================

String sessionID = "";

bool ready = false;

unsigned long lastHostHeartbeat = 0;
unsigned long lastArduinoHeartbeat = 0;

unsigned long lastCommandSequence = 0;

String inputBuffer = "";


// ============================================================
// SAFE STOP
// ============================================================

void safeStop()
{
  digitalWrite(ACTUATOR_PIN, LOW);

  Serial.println("SAFE_STOP");
}


// ============================================================
// DEMO ACTUATOR
// ============================================================

void setActuator(long value)
{
  /*
     This is only a test.

     value = 0 -> actuator OFF
     value != 0 -> actuator ON

     Later replace this with your actual
     left/right motor driver code.
  */

  if (value == 0)
  {
    digitalWrite(ACTUATOR_PIN, LOW);
  }
  else
  {
    digitalWrite(ACTUATOR_PIN, HIGH);
  }
}


// ============================================================
// SEND IDENTITY
// ============================================================

void sendIdentity()
{
  Serial.print("IDENTITY ");
  Serial.print(DEVICE_ID);
  Serial.print(" ");
  Serial.print(CONTROLLER_ROLE);
  Serial.print(" ");
  Serial.print(FIRMWARE_VERSION);
  Serial.print(" ");
  Serial.println(PROTOCOL_VERSION);
}


// ============================================================
// SEND BOOT MESSAGE
// ============================================================

void sendBoot()
{
  Serial.print("BOOT ");
  Serial.print(DEVICE_ID);
  Serial.print(" ");
  Serial.print(CONTROLLER_ROLE);
  Serial.print(" ");
  Serial.print(FIRMWARE_VERSION);
  Serial.print(" ");
  Serial.println(PROTOCOL_VERSION);
}


// ============================================================
// SEND HEARTBEAT
// ============================================================

void sendHeartbeat()
{
  Serial.print("HB ");
  Serial.print(DEVICE_ID);
  Serial.print(" ");
  Serial.print(CONTROLLER_ROLE);
  Serial.print(" ");
  Serial.println(millis());
}


// ============================================================
// IDENTIFY
// ============================================================

void handleIdentify(int requestedProtocol)
{
  if (requestedProtocol != PROTOCOL_VERSION)
  {
    Serial.println("ERR PROTOCOL_MISMATCH");
    return;
  }

  sendIdentity();
}


// ============================================================
// ARM
// ============================================================

void handleArm(String newSession)
{
  if (newSession.length() == 0)
  {
    Serial.println("ERR EMPTY_SESSION");
    return;
  }

  /*
     ARM creates a completely new session.

     Therefore an old session cannot be reused
     after reconnecting.
  */

  sessionID = newSession;

  ready = true;

  lastHostHeartbeat = millis();

  // Reset command sequence for new session
  lastCommandSequence = 0;

  // Always start a new session stopped
  safeStop();

  Serial.print("READY ");
  Serial.print(DEVICE_ID);
  Serial.print(" ");
  Serial.println(sessionID);
}


// ============================================================
// HOST HEARTBEAT
// ============================================================

void handleHeartbeat(String receivedSession)
{
  if (!ready)
  {
    Serial.println("ERR NOT_READY");
    return;
  }

  if (receivedSession != sessionID)
  {
    Serial.println("ERR BAD_SESSION");
    return;
  }

  // Host is alive
  lastHostHeartbeat = millis();
}


// ============================================================
// COMMAND
// ============================================================

void handleCommand(
  String receivedSession,
  unsigned long sequence,
  long value
)
{
  // ----------------------------------------
  // Check READY
  // ----------------------------------------

  if (!ready)
  {
    Serial.println("CMD_REJECT NOT_READY");
    return;
  }


  // ----------------------------------------
  // Check SESSION
  // ----------------------------------------

  if (receivedSession != sessionID)
  {
    Serial.println("CMD_REJECT BAD_SESSION");
    return;
  }


  // ----------------------------------------
  // Check SEQUENCE
  // ----------------------------------------

  if (sequence <= lastCommandSequence)
  {
    Serial.println("CMD_REJECT STALE_OR_DUPLICATE");
    return;
  }


  // New command accepted
  lastCommandSequence = sequence;


  // Execute command
  setActuator(value);


  // Acknowledge
  Serial.print("CMD_OK ");
  Serial.println(sequence);
}


// ============================================================
// DISARM
// ============================================================

void handleDisarm(String receivedSession)
{
  if (receivedSession != sessionID)
  {
    Serial.println("ERR BAD_SESSION");
    return;
  }

  ready = false;

  sessionID = "";

  safeStop();

  Serial.println("DISARMED");
}


// ============================================================
// PROCESS COMMAND
// ============================================================

void processCommand(String line)
{
  line.trim();

  if (line.length() == 0)
  {
    return;
  }


  // ========================================================
  // IDENTIFY
  // ========================================================

  if (line.startsWith("IDENTIFY "))
  {
    String protocolString = line.substring(9);

    int protocol = protocolString.toInt();

    handleIdentify(protocol);

    return;
  }


  // ========================================================
  // ARM
  // ========================================================

  if (line.startsWith("ARM "))
  {
    String session = line.substring(4);

    handleArm(session);

    return;
  }


  // ========================================================
  // HEARTBEAT
  // ========================================================

  if (line.startsWith("HB "))
  {
    String session = line.substring(3);

    handleHeartbeat(session);

    return;
  }


  // ========================================================
  // DISARM
  // ========================================================

  if (line.startsWith("DISARM "))
  {
    String session = line.substring(7);

    handleDisarm(session);

    return;
  }


  // ========================================================
  // COMMAND
  //
  // CMD SESSION_ID SEQUENCE VALUE
  //
  // Example:
  //
  // CMD TEST123 1 1
  // ========================================================

  if (line.startsWith("CMD "))
  {
    String remaining = line.substring(4);


    // Find first space
    int firstSpace = remaining.indexOf(' ');

    if (firstSpace == -1)
    {
      Serial.println("CMD_REJECT MALFORMED");
      return;
    }


    // Find second space
    int secondSpace =
      remaining.indexOf(' ', firstSpace + 1);

    if (secondSpace == -1)
    {
      Serial.println("CMD_REJECT MALFORMED");
      return;
    }


    // Extract fields
    String session =
      remaining.substring(0, firstSpace);

    String sequenceString =
      remaining.substring(
        firstSpace + 1,
        secondSpace
      );

    String valueString =
      remaining.substring(secondSpace + 1);


    unsigned long sequence =
      sequenceString.toInt();

    long value =
      valueString.toInt();


    handleCommand(
      session,
      sequence,
      value
    );

    return;
  }


  // ========================================================
  // UNKNOWN COMMAND
  // ========================================================

  Serial.println("ERR UNKNOWN_COMMAND");
}


// ============================================================
// READ SERIAL
// ============================================================

void readSerial()
{
  while (Serial.available() > 0)
  {
    char c = Serial.read();


    if (c == '\n')
    {
      processCommand(inputBuffer);

      inputBuffer = "";
    }
    else if (c != '\r')
    {
      inputBuffer += c;
    }
  }
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  pinMode(
    ACTUATOR_PIN,
    OUTPUT
  );


  // Always start safe
  safeStop();


  ready = false;

  sessionID = "";


  lastHostHeartbeat = millis();

  lastArduinoHeartbeat = millis();


  delay(500);


  // Tell laptop who we are
  sendBoot();

  sendIdentity();
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
  // Read commands from laptop
  readSerial();


  unsigned long now = millis();


  // ========================================================
  // ARDUINO HEARTBEAT
  // ========================================================

  if (
    now - lastArduinoHeartbeat
    >= ARDUINO_HEARTBEAT_PERIOD
  )
  {
    sendHeartbeat();

    lastArduinoHeartbeat = now;
  }


  // ========================================================
  // HOST WATCHDOG
  // ========================================================

  if (ready)
  {
    if (
      now - lastHostHeartbeat
      >= HOST_HEARTBEAT_TIMEOUT
    )
    {
      Serial.println(
        "ERR HOST_HEARTBEAT_TIMEOUT"
      );


      // Host disappeared -> stop
      ready = false;

      sessionID = "";

      safeStop();


      // Prevent repeated timeout messages
      lastHostHeartbeat = now;
    }
  }


  delay(2);
}
