package com.foryourfarm.backend.domain.actioncard;

import com.foryourfarm.backend.domain.crop.CropType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 행동카드 카탈로그 — 시드로만 적재, 런타임 수정 없음(DB.md §3.12).
 * id는 시드가 고정 부여하므로 @GeneratedValue 없음.
 * applicableCropType == null이면 TREE/FIELD 공통 카드.
 * triggerWeekMin/Max는 밭의 경과 주수(currentWeek - plantedAtWeek) 기준 노출 구간 — 둘 다 null이면 상시 노출.
 */
@Entity
@Table(name = "action_card")
@Getter
@NoArgsConstructor
public class ActionCard {

    @Id
    private Integer id;

    @Column(nullable = false, length = 30)
    private String code;

    @Column(nullable = false, length = 50)
    private String label;

    @Enumerated(EnumType.STRING)
    @Column(name = "applicable_crop_type", length = 10)
    private CropType applicableCropType;

    @Column(name = "trigger_week_min")
    private Integer triggerWeekMin;

    @Column(name = "trigger_week_max")
    private Integer triggerWeekMax;

    @Column(columnDefinition = "TEXT")
    private String description;
}
