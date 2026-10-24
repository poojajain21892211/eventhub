from rest_framework import status
from rest_framework.test import APITestCase

from .models import Event, Reservation


class EventHubAPITests(APITestCase):

    def setUp(self):
        self.event = Event.objects.create(
            title="AI Engineering Summit 2026",
            venue="HITEX Exhibition Centre, Hyderabad",
            date="2026-12-12",
            total_seats=5,
            available_seats=5,
            status="upcoming",
        )

    def test_create_event(self):
        data = {
            "title": "Python Conference 2026",
            "venue": "Bangalore Convention Centre",
            "date": "2026-12-20",
            "total_seats": 100,
            "available_seats": 100,
            "status": "upcoming",
        }

        response = self.client.post(
            "/api/events/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["reservations_count"],
            0,
        )

    def test_available_seats_cannot_exceed_total_seats(self):
        data = {
            "title": "Invalid Event",
            "venue": "Hyderabad",
            "date": "2026-12-20",
            "total_seats": 5,
            "available_seats": 10,
            "status": "upcoming",
        }

        response = self.client.post(
            "/api/events/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_successful_reservation_deducts_seats(self):
        data = {
            "event": self.event.id,
            "attendee_name": "Priya Sharma",
            "attendee_email": "priya@example.com",
            "seats_reserved": 4,
        }

        response = self.client.post(
            "/api/reservations/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["status"],
            "confirmed",
        )

        self.event.refresh_from_db()

        self.assertEqual(
            self.event.available_seats,
            1,
        )

    def test_overbooking_returns_400(self):
        self.event.available_seats = 1
        self.event.save()

        data = {
            "event": self.event.id,
            "attendee_name": "Rohan Mehta",
            "attendee_email": "rohan@example.com",
            "seats_reserved": 2,
        }

        response = self.client.post(
            "/api/reservations/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.event.refresh_from_db()

        self.assertEqual(
            self.event.available_seats,
            1,
        )

        self.assertEqual(
            Reservation.objects.count(),
            0,
        )

    def test_completed_event_cannot_be_reserved(self):
        self.event.status = "completed"
        self.event.save()

        data = {
            "event": self.event.id,
            "attendee_name": "Priya Sharma",
            "attendee_email": "priya@example.com",
            "seats_reserved": 1,
        }

        response = self.client.post(
            "/api/reservations/",
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_cancel_reservation_restores_seats(self):
        reservation = Reservation.objects.create(
            event=self.event,
            attendee_name="Priya Sharma",
            attendee_email="priya@example.com",
            seats_reserved=4,
            status="confirmed",
        )

        self.event.available_seats = 1
        self.event.save()

        response = self.client.post(
            f"/api/reservations/{reservation.id}/cancel/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.event.refresh_from_db()
        reservation.refresh_from_db()

        self.assertEqual(
            self.event.available_seats,
            5,
        )

        self.assertEqual(
            reservation.status,
            "cancelled",
        )

    def test_double_cancellation_returns_400(self):
        reservation = Reservation.objects.create(
            event=self.event,
            attendee_name="Priya Sharma",
            attendee_email="priya@example.com",
            seats_reserved=4,
            status="cancelled",
        )

        original_available_seats = self.event.available_seats

        response = self.client.post(
            f"/api/reservations/{reservation.id}/cancel/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.event.refresh_from_db()

        self.assertEqual(
            self.event.available_seats,
            original_available_seats,
        )

    def test_filter_events_by_status(self):
        response = self.client.get(
            "/api/events/?status=upcoming"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["status"],
            "upcoming",
        )

    def test_filter_events_by_venue(self):
        response = self.client.get(
            "/api/events/?venue=hyderabad"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    def test_filter_reservations_by_event_id(self):
        Reservation.objects.create(
            event=self.event,
            attendee_name="Priya Sharma",
            attendee_email="priya@example.com",
            seats_reserved=2,
        )

        response = self.client.get(
            f"/api/reservations/?event_id={self.event.id}"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["event"],
            self.event.id,
        )