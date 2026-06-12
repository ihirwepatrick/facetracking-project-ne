# Integrated Assessment 1

# AI-Powered Single-Speaker Face Recognition and Camera Tracking System

## 1. Project Background

**BENAX Technologies Ltd** is developing an intelligent camera control system designed for live presentations, lectures, conferences, performances, and video-conferencing environments.

Traditional face-tracking systems automatically follow any detected face within the camera view. In contrast, this project requires the camera to identify, lock onto, and continuously follow a single pre-enrolled speaker while ignoring all other individuals appearing in the frame.

The solution combines concepts from:

* Artificial Intelligence and Machine Learning
* Computer Vision
* Embedded Systems
* Networking and IoT Communication
* Motor Control
* Power Electronics
* System Integration

Students are required to design, implement, integrate, test, and demonstrate a complete working prototype.

---

# 2. System Overview

The system consists of two major components:

### AI Processing Unit (PC/Laptop)

Responsible for:

* Capturing video from a USB camera
* Detecting faces
* Recognizing the enrolled speaker
* Tracking the speaker's position
* Generating movement commands
* Publishing commands through MQTT
* Logging operational data

### Embedded Control Unit (ESP8266)

Responsible for:

* Connecting to Wi-Fi
* Subscribing to MQTT messages
* Receiving movement commands
* Driving the servo motor
* Positioning the camera accordingly

### Camera Motion System

Responsible for:

* Rotating the camera horizontally
* Maintaining the speaker at the center of the frame
* Providing smooth and stable movement

---

# 3. Assessment Objective

Design and implement a complete **AI-Powered Single-Speaker Face Recognition and Camera Tracking System** capable of:

1. Enrolling a single authorized speaker.
2. Recognizing only the enrolled speaker.
3. Ignoring all other detected faces.
4. Tracking the speaker in real time.
5. Generating movement commands based on tracking position.
6. Transmitting commands using MQTT.
7. Controlling a servo motor through ESP8266.
8. Logging operational evidence.
9. Demonstrating reliable operation under realistic conditions.

---

# 4. Functional Requirements

## 4.1 Speaker Enrollment

The system shall provide a mechanism for registering one authorized speaker.

### Requirements

* Capture between 10 and 30 facial images.
* Allow images from different angles and expressions.
* Generate a reusable facial profile (embedding/template).
* Store the profile locally for future recognition.

### Deliverables

* Enrollment interface or script.
* Stored facial profile/template.
* Evidence showing successful enrollment.

---

## 4.2 Single-Speaker Recognition (Speaker Lock)

The system shall recognize only the enrolled speaker.

### Requirements

* Detect faces in each camera frame.
* Compare detected faces against the enrolled profile.
* Identify the authorized speaker.
* Ignore all non-enrolled individuals.
* Display recognition confidence in real time.

### Deliverables

* Working face recognition module.
* Real-time display showing:

  * Speaker identity
  * Confidence score
* Demonstration with multiple people in view.

---

## 4.3 Face Tracking and Motion Control Logic

The system shall continuously track the enrolled speaker.

### Requirements

* Determine speaker position within the frame.
* Calculate horizontal tracking error.
* Convert error into motion commands.
* Reduce unnecessary servo jitter using smoothing or dead-band logic.

### Expected Commands

* LEFT
* RIGHT
* STOP
* SCAN

### Deliverables

* Tracking algorithm implementation.
* Command generation module.
* Flowchart showing:

```text
Face Detection
      ↓
Face Recognition
      ↓
Speaker Tracking
      ↓
Error Calculation
      ↓
Command Generation
      ↓
MQTT Publishing
```

---

## 4.4 MQTT Communication

The system shall communicate between the AI module and the embedded controller using MQTT.

### Requirements

* Publish movement commands from the PC.
* Subscribe to commands on the ESP8266.
* Maintain reliable communication over Wi-Fi.

### Deliverables

* MQTT configuration.
* Demonstration of command transmission.
* Evidence of successful publishing and subscription.

---

## 4.5 Embedded Servo Control

The ESP8266 shall control the servo motor based on received commands.

### Requirements

* Interpret MQTT commands.
* Generate appropriate servo signals.
* Rotate camera smoothly.
* Maintain stable operation.

### Deliverables

* ESP8266 firmware.
* Servo control implementation.
* Wiring diagram.
* Demonstration of camera movement.

---

## 4.6 Logging and Operational Evidence

The system shall maintain operational logs.

### Information to Log

* Speaker identity
* Confidence score
* Timestamp
* Published command
* System events

### Deliverables

* Log file (CSV, JSON, or equivalent)
* Evidence of recorded system activity
* Sample log outputs

---

# 5. Robustness Requirements

The completed system must demonstrate the following behaviors.

## Scenario 1: Multiple Faces

When additional people enter the frame:

* The camera must continue tracking only the enrolled speaker.
* Other faces must be ignored.

## Scenario 2: Temporary Occlusion

When the speaker is partially or fully hidden:

* The system should enter search mode.
* Tracking should resume automatically once visibility is restored.

## Scenario 3: Continuous Movement

When the speaker moves:

* The camera should smoothly follow.
* Motion should remain stable without excessive oscillation.

### Deliverables

Video or live demonstration of all three scenarios.

---

# 6. Hardware Requirements

## Vision System

* USB Camera

Used for:

* Face detection
* Face recognition
* Face tracking

---

## Motion System

* Servo Motor

Used for:

* Horizontal camera rotation
* Target positioning

---

## Embedded Controller

* ESP8266

Used for:

* MQTT communication
* Servo control

---

## Mechanical Structure

* Camera mounting platform
* Servo mounting mechanism
* Smooth horizontal rotation support
* Manual tilt adjustment mechanism

---

## Computing Platform

* Desktop or Laptop

Used for:

* AI processing
* MQTT communication
* Development and testing

---

# 7. Software Requirements

## Programming Environment

* Python 3.10+

## Recommended Libraries

### Computer Vision

* OpenCV

### Face Recognition

* Face Recognition Library or equivalent ML solution

### MQTT Communication

* Mosquitto Broker
* paho-mqtt

### Data Processing

* NumPy
* Pandas

### Storage

* CSV
* JSON

---

# 8. Required Documentation Deliverables

Each team must submit the following:

## A. System Design Document

Must include:

* Problem understanding
* System architecture
* Component descriptions
* Data flow explanation

---

## B. Block Diagram

Illustrating:

* Camera
* AI Processing Unit
* MQTT Communication
* ESP8266
* Servo Motor

---

## C. Flowchart

Showing:

* Recognition
* Tracking
* Command generation
* Motor control process

---

## D. Hardware Wiring Diagram

Showing:

* ESP8266 connections
* Servo connections
* Power connections

---

## E. Source Code

Including:

* Enrollment module
* Recognition module
* Tracking module
* MQTT module
* ESP8266 firmware

---

## F. Testing Evidence

Including screenshots, logs, and demonstration results.

---

# 9. Final Demonstration Requirements

Teams must demonstrate:

### Test 1

Successful speaker enrollment.

### Test 2

Recognition of the enrolled speaker.

### Test 3

Ignoring non-enrolled individuals.

### Test 4

Real-time camera tracking.

### Test 5

MQTT communication.

### Test 6

Servo motor response.

### Test 7

Speaker re-acquisition after occlusion.

### Test 8

Operational log generation.

---

# 10. Assessment Outputs

At the end of the assessment, each team shall provide:

1. Fully functioning integrated system.
2. Source code repository.
3. System design documentation.
4. Architecture diagram.
5. Flowchart.
6. Wiring diagram.
7. Operational log files.
8. Demonstration evidence.
9. Presentation of system functionality.

---

# Time Allowed

**6 Hours**

---

# Materials Provided

* FalconEye V1 HD Camera Board
* ESP8266 Development Board
* Servo Motor
* 2-DOF Camera Mechanism
* Micro-USB Cables
* Male-to-Female Jumper Wires
* USB Hub
