package com.foryourfarm.backend.domain.region;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;

/**
 * 마스터 데이터 — 시드로만 적재, 런타임 수정 없음(DB.md §1).
 * id는 시드가 고정 부여하므로 @GeneratedValue 없음(마이그레이션의 region.id INT PK와 동일).
 */
@Entity
@Table(name = "region")
@Getter
@NoArgsConstructor
public class Region {

    @Id
    private Integer id;

    @Column(nullable = false, length = 50)
    private String name;

    @Column(nullable = false, length = 30)
    private String sido;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;
}
