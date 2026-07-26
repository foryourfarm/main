"""질문 문장에서 작물명 자동 인식(detect_crop_from_text)의 정확도·오탐 방지 검증.

"배"는 한 글자라 "재배"·"배수" 같은 무관한 단어에 오탐하기 쉬운 게 이 로직의 핵심 리스크다.

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_chat_crop_detection   (backend/ 에서)
"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Crop
from app.services.chat_service import detect_crop_from_text


class TestDetectCropFromText(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Crop.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Crop(id=1, name="사과"),
                Crop(id=2, name="배"),
                Crop(id=3, name="오이"),
                Crop(id=4, name="감자"),
                Crop(id=5, name="상추"),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_multichar_crop_name_matches_by_substring(self):
        self.assertEqual(detect_crop_from_text(self.db, "사과나무 병충해 알려줘"), 1)
        self.assertEqual(detect_crop_from_text(self.db, "감자 파종 시기는?"), 4)

    def test_pear_matches_common_forms(self):
        self.assertEqual(detect_crop_from_text(self.db, "배는 어떤 토양이 좋아?"), 2)
        self.assertEqual(detect_crop_from_text(self.db, "배나무 병충해 알려줘"), 2)
        self.assertEqual(detect_crop_from_text(self.db, "배 재배 방법 알려줘"), 2)
        self.assertEqual(detect_crop_from_text(self.db, "배"), 2)

    def test_pear_does_not_false_positive_on_unrelated_words(self):
        # "재배"·"배수"에 "배"가 부분문자열로 들어있지만 배(과일) 얘기가 아니다.
        # (다른 작물명이 같이 있으면 그게 먼저 잡히므로, 다른 작물명이 없는 문장으로 확인한다.)
        self.assertIsNone(detect_crop_from_text(self.db, "요즘 재배가 잘 안 돼요"))
        self.assertIsNone(detect_crop_from_text(self.db, "배수가 잘 안 돼요"))

    def test_unsupported_crop_returns_none(self):
        self.assertIsNone(detect_crop_from_text(self.db, "토마토 재배 방법 알려줘"))


if __name__ == "__main__":
    unittest.main()
