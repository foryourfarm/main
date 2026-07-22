package com.foryourfarm.backend.domain.crop;

/**
 * TREE(사과, 배) = 게임 시작부터 이미 성숙 상태, 성장 추적 없음.
 * FIELD(오이, 감자, 상추) = 심은 시점부터 경과 주수에 따라 생육(PRD.md §15).
 */
public enum CropType {
    TREE,
    FIELD
}
