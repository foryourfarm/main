package com.foryourfarm.backend.api;

/**
 * 공통 응답 래퍼 (CLAUDE.md §6). 컨트롤러는 항상 이 타입으로 응답한다.
 */
public record ApiResponse<T>(boolean success, T data, ApiError error) {

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(true, data, null);
    }

    public static <T> ApiResponse<T> fail(String code, String message) {
        return new ApiResponse<>(false, null, new ApiError(code, message));
    }

    public record ApiError(String code, String message) {}
}
