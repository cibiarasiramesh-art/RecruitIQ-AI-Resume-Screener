import unittest

from app import build_ai_payload


class BuildAIPayloadTest(unittest.TestCase):
    def test_build_ai_payload_normalizes_list_skills_for_frontend(self):
        payload = build_ai_payload(
            {
                "matched_skills": ["Python", "Flask"],
                "missing_skills": ["Docker", "Kubernetes"],
                "recommendation": "Good Match",
                "learning_roadmap": ["Learn Docker"],
            },
            {"improvement_plan": ["Improve your resume"]},
        )

        self.assertIsInstance(payload["matched_skills"], dict)
        self.assertIsInstance(payload["missing_skills"], dict)
        self.assertEqual(payload["matched_skills"]["General"], ["Python", "Flask"])
        self.assertEqual(payload["missing_skills"]["General"], ["Docker", "Kubernetes"])
        self.assertEqual(payload["learning_roadmap"], ["Learn Docker"])


if __name__ == "__main__":
    unittest.main()
