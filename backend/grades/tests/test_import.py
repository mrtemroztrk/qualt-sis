from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from grades.models import Grade

from .test_teaching import BASE, TeachingWorld


class GradeImportTests(TeachingWorld, TestCase):
    def setUp(self):
        self.build_grading_world()
        self.midterm = self.component("Midterm", "30")
        self.url = f"{BASE}/components/{self.midterm.pk}/grades/import/"

    def upload(self, text, client=None):
        file = SimpleUploadedFile("grades.csv", text.encode("utf-8"), content_type="text/csv")
        return (client or self.client).post(self.url, {"file": file}, format="multipart")

    def test_semicolon_file_with_decimal_comma(self):
        response = self.upload("student_no;first_name;score\n1001;Ali;85,5\n1002;Ayşe;70\n")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["missing_grades"], 0)
        scores = dict(Grade.objects.values_list("student__student_no", "score"))
        self.assertEqual(scores, {"1001": Decimal("85.5"), "1002": Decimal("70")})

    def test_comma_file_with_byte_order_mark_and_capitalised_headers(self):
        response = self.upload("﻿Student_No,Score\n1001,90\n")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Grade.objects.get().score, Decimal("90"))

    def test_rows_with_an_empty_score_are_skipped(self):
        response = self.upload("student_no;score\n1001;60\n1002;\n")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["missing_grades"], 1)

    def test_errors_name_the_file_line(self):
        response = self.upload("student_no;score\n1001;60\n9999;70\n1003;80\n1002;abc\n")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data["file"]), {"3", "4", "5"})
        self.assertFalse(Grade.objects.exists())

    def test_score_above_maximum_names_the_line(self):
        response = self.upload("student_no;score\n1001;60\n1002;120\n")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data["file"]), {"3"})
        self.assertFalse(Grade.objects.exists())

    def test_missing_columns_or_file(self):
        self.assertEqual(self.upload("number;points\n1001;60\n").status_code, 400)
        self.assertEqual(self.upload("").status_code, 400)
        self.assertEqual(self.client.post(self.url, {}, format="multipart").status_code, 400)

    def test_other_instructors_cannot_import(self):
        response = self.upload("student_no;score\n1001;60\n", client=self.client_for(self.other_instructor))
        self.assertEqual(response.status_code, 404)

    def test_template_lists_the_roster_with_current_scores(self):
        Grade.objects.create(component=self.midterm, student=self.student, score=Decimal("85"))
        response = self.client.get(f"{BASE}/components/{self.midterm.pk}/grades/template/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn('filename="CSE-301-1-Midterm.csv"', response["Content-Disposition"])
        lines = response.content.decode("utf-8-sig").splitlines()
        self.assertEqual(lines[0], "student_no;first_name;last_name;score")
        self.assertEqual([line.split(";")[0] for line in lines[1:]], ["1001", "1002"])
        self.assertTrue(lines[1].endswith(";85.00"))

    def test_template_round_trips_through_import(self):
        Grade.objects.create(component=self.midterm, student=self.student, score=Decimal("85"))
        template = self.client.get(f"{BASE}/components/{self.midterm.pk}/grades/template/").content.decode("utf-8")
        filled = template.replace("\r\n", "\n").rstrip("\n") + "77,25\n"
        response = self.upload(filled)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Grade.objects.get(student=self.other_student).score, Decimal("77.25"))
