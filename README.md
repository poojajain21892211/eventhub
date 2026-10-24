# EventHub - Event Ticketing REST API

EventHub is a backend REST API for a simplified event ticketing platform, built with Django and Django REST Framework.

The API supports event discovery and reservation lifecycle management, including seat reservation, overbooking protection, cancellation, and seat-capacity restoration. The implementation uses Django ORM for persistence, DRF serializers for validation, `ModelViewSet` for resource operations, `DefaultRouter` for API routing, and custom middleware for request logging.

---

## Architecture Overview

EventHub follows a lightweight layered Django REST architecture:

```text
Client / Postman / DRF Browsable API
                |
                v
        URL Configuration
                |
                v
            DRF Router
                |
                v
             ViewSets
                |
                v
            Serializers
       Validation + Mapping
                |
                v
          Django Models
                |
                v
           Django ORM
                |
                v
              SQLite
```

Request logging is implemented as a cross-cutting middleware concern:

```text
Request
   |
   v
RequestLoggingMiddleware
   |
   v
Router -> ViewSet -> Serializer -> ORM
   |
   v
Response
   |
   v
RequestLoggingMiddleware
```

This separation keeps persistence, API validation, request orchestration, URL routing, and request logging in clearly defined components.

---

## Core Capabilities

EventHub supports:

- Creating, retrieving, updating, and deleting Events
- Browsing Events
- Filtering Events by status
- Filtering Events by venue
- Creating seat Reservations
- Validating requested seat quantities
- Preventing overbooking
- Restricting Reservations based on Event lifecycle status
- Cancelling Reservations
- Restoring seats following cancellation
- Preventing duplicate cancellation
- Filtering Reservations by Event ID
- Returning the number of confirmed Reservation records for an Event
- Logging HTTP method, request path, response status, and processing duration

---

## Domain Model

### Event

An Event represents a ticketed event and owns the seat-capacity state.

| Field | Purpose |
|---|---|
| `id` | Auto-generated primary key |
| `title` | Event title |
| `venue` | Event location |
| `date` | Scheduled Event date |
| `total_seats` | Total capacity |
| `available_seats` | Seats currently available |
| `status` | Event lifecycle status |
| `created_at` | Automatically generated creation timestamp |

Supported Event statuses:

- `upcoming`
- `ongoing`
- `completed`
- `cancelled`

Events are ordered by `date` by default.

### Reservation

A Reservation represents seats reserved by an attendee for a specific Event.

| Field | Purpose |
|---|---|
| `id` | Auto-generated primary key |
| `event` | Foreign-key reference to an Event |
| `attendee_name` | Name of the attendee |
| `attendee_email` | Email address of the attendee |
| `seats_reserved` | Number of reserved seats |
| `status` | Reservation lifecycle status |
| `created_at` | Automatically generated creation timestamp |

Supported Reservation statuses:

- `confirmed`
- `cancelled`

Reservations are ordered by `created_at` in descending order by default.

### Relationship

```text
Event 1 ---------------- * Reservation
```

One Event can have multiple Reservations, while each Reservation belongs to one Event. The relationship is implemented with a Django `ForeignKey` using `related_name="reservations"` and `on_delete=models.CASCADE`.

---

## Component Responsibilities

### Models

`events/models.py`

The models define the persistent domain entities, lifecycle status choices, default ordering, and the one-to-many relationship between Event and Reservation. Django ORM provides the persistence abstraction over SQLite.

### Serializers

`events/serializers.py`

Serializers form the API validation and representation boundary.

`EventSerializer`:

- Maps Event records to and from API representations
- Exposes the computed `reservations_count` field
- Ensures `available_seats` does not exceed `total_seats`

`ReservationSerializer`:

- Requires at least one seat
- Allows Reservations only for `upcoming` or `ongoing` Events
- Checks current seat availability
- Rejects overbooking attempts
- Reduces `available_seats` when a Reservation is created
- Treats `status` and `created_at` as read-only API fields

### ViewSets

`events/views.py`

DRF `ModelViewSet` provides standard resource operations while keeping HTTP orchestration separate from persistence and validation.

`EventViewSet` supports filtering by:

- `status`
- `venue`

`ReservationViewSet` supports filtering by:

- `event_id`

It also exposes a custom cancellation operation using DRF's `@action` decorator.

### Routing

`events/urls.py`

DRF `DefaultRouter` maps the Event and Reservation ViewSets to REST endpoints and generates the standard CRUD routes.

### Middleware

`events/middleware.py`

`RequestLoggingMiddleware` records:

- HTTP method
- Request path
- HTTP response status
- Request-processing duration

Example console output:

```text
POST /api/reservations/ - 201 - 0.01s
```

---

## API Endpoints

### Event APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events/` | List Events |
| POST | `/api/events/` | Create an Event |
| GET | `/api/events/{id}/` | Retrieve an Event |
| PUT | `/api/events/{id}/` | Replace an Event |
| PATCH | `/api/events/{id}/` | Partially update an Event |
| DELETE | `/api/events/{id}/` | Delete an Event |
| GET | `/api/events/?status=upcoming` | Filter Events by status |
| GET | `/api/events/?venue=Hyderabad` | Filter Events by venue using a case-insensitive partial match |

### Reservation APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/reservations/` | List Reservations |
| POST | `/api/reservations/` | Create a Reservation |
| GET | `/api/reservations/{id}/` | Retrieve a Reservation |
| PUT | `/api/reservations/{id}/` | Replace a Reservation |
| PATCH | `/api/reservations/{id}/` | Partially update a Reservation |
| DELETE | `/api/reservations/{id}/` | Delete a Reservation |
| GET | `/api/reservations/?event_id={id}` | Filter Reservations by Event ID |
| POST | `/api/reservations/{id}/cancel/` | Cancel a Reservation and restore its seats |

### Expected Status Codes

| Scenario | Expected status |
|---|---|
| Create Event | `201 Created` |
| List or retrieve resources | `200 OK` |
| Create Reservation | `201 Created` |
| Overbooking attempt | `400 Bad Request` |
| Successful cancellation | `200 OK` |
| Duplicate cancellation | `400 Bad Request` |
| Unknown resource | `404 Not Found` |

---

## Business Rules

EventHub enforces the following rules:

1. At least one seat must be included in a Reservation.
2. Reservations are accepted only for `upcoming` or `ongoing` Events.
3. Requested seats cannot exceed the Event's current `available_seats` value.
4. Creating a Reservation reduces the associated Event's available capacity.
5. Cancelling a Reservation restores its reserved seats to the Event.
6. A cancelled Reservation cannot be cancelled again.
7. An Event's `available_seats` value cannot exceed `total_seats`.
8. `reservations_count` represents confirmed Reservation records, not the number of reserved seats.

For example, one confirmed Reservation containing four seats produces:

```json
{
  "reservations_count": 1
}
```

---

## Reservation Lifecycle

### Reservation Creation

```text
POST Reservation
       |
       v
Validate seat quantity
       |
       v
Validate Event status
       |
       v
Check available capacity
       |
       v
Deduct available seats
       |
       v
Create Reservation
       |
       v
Return 201 Created
```

### Overbooking Protection

```text
Requested seats > Available seats
              |
              v
         Validation fails
              |
              v
        400 Bad Request
              |
              v
     No Reservation created
              |
              v
       Capacity unchanged
```

### Reservation Cancellation

```text
POST Cancel
     |
     v
Load Reservation
     |
     v
Already cancelled?
   /             \
 Yes              No
  |                |
  v                v
400          Restore seats
                   |
                   v
            Mark cancelled
                   |
                   v
               Return 200
```

A cancelled Reservation remains persisted as a lifecycle record, while its status changes from `confirmed` to `cancelled`.

---

## Key Design Decision

### Reservation validation and seat adjustment at the serializer boundary

Reservation-specific validation and creation behavior is centralized in `ReservationSerializer`.

Before a Reservation is created, the serializer validates:

- Requested seat quantity
- Event lifecycle status
- Current seat availability

After successful validation, the serializer reduces the Event's `available_seats` value and creates the Reservation.

This keeps HTTP request orchestration within the ViewSet while concentrating Reservation validation and creation behavior at the serializer boundary, consistent with the scope and prescribed design of this implementation.

---

## Production Considerations

The current implementation follows the project requirement of updating seat availability from the serializer's `create()` method.

It does not guarantee concurrency safety when multiple requests attempt to reserve the final available seats at the same time. A production implementation should treat availability validation, seat deduction, and Reservation creation as one transactional consistency boundary.

Django `transaction.atomic()` together with an appropriate database row-locking or concurrency-control strategy should be considered for that scenario. Transactional concurrency control is a production recommendation and is not implemented in this assignment.

Additional production concerns could include authentication, authorization, pagination, audit logging, structured monitoring, and a production-grade database. These are outside the current project scope.

---

## Testing Strategy

EventHub was verified with automated API tests and manual Postman testing.

### Automated API Tests

Focused tests in `events/tests.py` validate:

- Event creation
- Event capacity validation
- Successful Reservation creation
- Seat deduction after Reservation creation
- Overbooking rejection
- Rejection of Reservations for completed Events
- Reservation cancellation
- Seat restoration after cancellation
- Duplicate-cancellation protection
- Event filtering by status
- Event filtering by venue
- Reservation filtering by Event ID

Run the test suite with:

```bash
python manage.py test
```

Django creates a temporary test database for the suite, so automated tests do not modify the normal development database.

### Manual Postman Verification

Postman was used to verify the required end-to-end HTTP scenarios:

- Successful Reservation returning `201 Created`
- Overbooking rejection returning `400 Bad Request`
- Successful cancellation returning `200 OK`
- Seat deduction after Reservation creation
- Seat restoration after cancellation
- Event filtering by status and venue
- Reservation filtering by Event ID
- Middleware logging for successful and failed requests

---

## Postman Verification

> Replace each placeholder below with the corresponding image reference after uploading or pasting the screenshot through GitHub's README editor.

### Successful Reservation - 201 Created

<!-- Insert successful-reservation Postman screenshot here -->

A confirmed Reservation is created and its reserved seats are deducted from the associated Event.

### Overbooking Protection - 400 Bad Request

<!-- Insert overbooking-failure Postman screenshot here -->

The request is rejected because the requested seat quantity is greater than the Event's remaining capacity. The failed request does not create a Reservation or change seat availability.

### Successful Cancellation - 200 OK

<!-- Insert successful-cancellation Postman screenshot here -->

The Reservation status changes to `cancelled`, and its reserved seats are restored to the Event.

---

## Technology Stack

- Python
- Django
- Django REST Framework
- Django ORM
- SQLite
- Postman

---

## Project Structure

```text
eventhub/
├── manage.py
├── eventhub/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── events/
│   ├── migrations/
│   │   ├── __init__.py
│   │   └── 0001_initial.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── middleware.py
│   ├── models.py
│   ├── serializers.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── db.sqlite3
├── requirements.txt
└── README.md
```

---

## Setup and Run Instructions

### Prerequisites

- Python 3
- `pip`
- Git, when cloning the repository
- Postman, for manual API verification

### 1. Clone and enter the repository

```bash
git clone <repository-url>
cd eventhub
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```cmd
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Run system checks and automated tests

```bash
python manage.py check
python manage.py test
```

### 7. Start the development server

```bash
python manage.py runserver
```

The REST API is exposed under `/api/`. The project intentionally does not define a separate homepage at `/`.

---

## Example API Requests

### Create an Event

```http
POST /api/events/
Content-Type: application/json
```

```json
{
  "title": "AI Engineering Summit 2026",
  "venue": "HITEX Exhibition Centre, Hyderabad",
  "date": "2026-12-12",
  "total_seats": 5,
  "available_seats": 5,
  "status": "upcoming"
}
```

Expected response status:

```text
201 Created
```

### Create a Reservation

```http
POST /api/reservations/
Content-Type: application/json
```

```json
{
  "event": 1,
  "attendee_name": "Priya Sharma",
  "attendee_email": "priya@example.com",
  "seats_reserved": 4
}
```

Example successful response:

```json
{
  "id": 1,
  "event": 1,
  "attendee_name": "Priya Sharma",
  "attendee_email": "priya@example.com",
  "seats_reserved": 4,
  "status": "confirmed",
  "created_at": "2026-10-24T16:30:00Z"
}
```

Expected response status:

```text
201 Created
```

### Overbooking Response

If only one seat remains and two seats are requested, the API returns:

```json
{
  "non_field_errors": [
    "Only 1 seat(s) available."
  ]
}
```

Expected response status:

```text
400 Bad Request
```

### Cancel a Reservation

```http
POST /api/reservations/1/cancel/
```

No request body is required.

Example successful response:

```json
{
  "id": 1,
  "event": 1,
  "attendee_name": "Priya Sharma",
  "attendee_email": "priya@example.com",
  "seats_reserved": 4,
  "status": "cancelled",
  "created_at": "2026-10-24T16:30:00Z"
}
```

Expected response status:

```text
200 OK
```

### Duplicate Cancellation Response

```json
{
  "error": "Already cancelled."
}
```

Expected response status:

```text
400 Bad Request
```

---

## Final Validation

Before submission, the project was verified using:

```bash
python manage.py test
python manage.py check
python manage.py makemigrations --check
python manage.py showmigrations events
```

The implementation was also manually validated through Postman for Event creation, Event filters, successful Reservation creation, seat deduction, overbooking rejection, Reservation filtering, successful cancellation, seat restoration, duplicate-cancellation protection, and middleware logging.

---

## Summary

EventHub demonstrates a clear separation between persistence, API validation, HTTP orchestration, routing, and cross-cutting request logging.

The implementation remains intentionally lightweight for the project scope while highlighting an important architectural boundary: Event seat availability is shared mutable state. The current serializer-based workflow satisfies the assignment requirements, while a production solution would strengthen that consistency boundary with transactional concurrency controls.
