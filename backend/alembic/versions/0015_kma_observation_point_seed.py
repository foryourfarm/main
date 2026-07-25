"""Create and populate kma_observation_point table.

Revision ID: 0015_kma_observation_point_seed
Revises: 0014_region_grid_seed
Create Date: 2026-07-26 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015_kma_observation_point_seed"
down_revision = "0014_region_grid_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create kma_observation_point table and seed data."""
    # 1. 테이블 생성
    op.create_table(
        "kma_observation_point",
        sa.Column("point_code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("altitude", sa.Integer, nullable=False),
    )

    # 2. 샘플 데이터 (510개 지점 중 일부만 표시)
    # 실제 마이그레이션은 기상청 API 또는 공개 데이터에서 전체 510개 지점을 로드해야 함
    sample_data = [
        # (point_code, name, lat, lon, altitude)
        ("108", "서울", 37.5665, 126.9780, 86),
        ("131", "인천", 37.4563, 126.7052, 69),
        ("135", "동두천", 37.9023, 127.0611, 146),
        ("143", "파주", 37.7600, 126.7850, 75),
        ("146", "양주", 37.8183, 127.0611, 157),
        ("201", "춘천", 37.8811, 127.7306, 168),
        ("202", "강릉", 37.7514, 128.8913, 25),
        ("211", "강화", 37.6450, 126.4017, 54),
        ("212", "속초", 38.6036, 128.5914, 6),
        ("221", "홍천", 37.6857, 127.8789, 178),
        ("226", "태백", 37.1705, 128.9932, 795),
        ("232", "백령도", 37.9769, 124.6700, 37),
        ("235", "동해", 37.5222, 129.1147, 19),
        ("236", "울릉도", 37.4869, 130.8925, 43),
        ("242", "대구", 35.8719, 128.6014, 55),
        # ... 추가 510개 지점
        # 실제 구현: 기상청 getAwsStnLstTbl API 또는 CSV 파일 로드
    ]

    connection = op.get_bind()

    # 데이터 삽입
    for point_code, name, lat, lon, altitude in sample_data:
        op.execute(
            sa.text("""
                INSERT INTO kma_observation_point (point_code, name, lat, lon, altitude)
                VALUES (:point_code, :name, :lat, :lon, :altitude)
                ON CONFLICT (point_code) DO NOTHING
            """),
            {
                "point_code": point_code,
                "name": name,
                "lat": lat,
                "lon": lon,
                "altitude": altitude,
            },
        )

    print(f"Inserted {len(sample_data)} KMA observation points (샘플)")
    print(
        "⚠️ 주의: 실제 마이그레이션은 510개 전체 지점을 로드해야 합니다."
        " 기상청 API(getAwsStnLstTbl) 또는 공개 데이터 사용"
    )


def downgrade() -> None:
    """Drop kma_observation_point table."""
    op.drop_table("kma_observation_point")
