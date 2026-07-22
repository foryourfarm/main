package com.foryourfarm.backend;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * 스프링 컨텍스트가 뜨는지(Security/JPA/Flyway 설정이 서로 안 깨지는지) 확인하는 최소 체크.
 * 로컬 Postgres(docker compose up -d)가 떠 있어야 통과한다.
 */
@SpringBootTest
class BackendApplicationTests {

    @Test
    void contextLoads() {
    }
}
