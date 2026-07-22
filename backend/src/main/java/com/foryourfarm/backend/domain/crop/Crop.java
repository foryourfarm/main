package com.foryourfarm.backend.domain.crop;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 마스터 데이터 — 시드로만 적재, 런타임 수정 없음(DB.md §1).
 * id는 시드가 고정 부여하므로 @GeneratedValue 없음.
 * seasonWeeks는 FIELD만 의미 있다(TREE는 성장추적 자체가 없어 null, DB.md §3.6).
 */
@Entity
@Table(name = "crop")
@Getter
@NoArgsConstructor
public class Crop {

    @Id
    private Integer id;

    @Column(nullable = false, length = 30)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(name = "crop_type", nullable = false, length = 10)
    private CropType cropType;

    @Column(name = "season_weeks")
    private Integer seasonWeeks;
}
