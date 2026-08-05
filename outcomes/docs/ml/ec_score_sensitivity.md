# EC 1:5 척도 민감도

운영 EC 밴드와 점수는 변경하지 않았다. 흙토람 `elcd`가 1:5 비환산 원값인지 이미 ×5 환산된 값인지 미확정이다.

| scenario | crop_code | regions | measured_regions | penalized_regions | mean_score | penalized_measured_regions |
|---|---|---|---|---|---|---|
| api_already_x5 | 03001 | 150 | 103 | 0 | 100.0 | 0 |
| api_already_x5 | 04009 | 150 | 103 | 0 | 100.0 | 0 |
| api_already_x5 | 07001 | 150 | 103 | 0 | 100.0 | 0 |
| raw_1_to_5 | 03001 | 150 | 103 | 2 | 99.297 | 1 |
| raw_1_to_5 | 04009 | 150 | 103 | 2 | 99.297 | 1 |
| raw_1_to_5 | 07001 | 150 | 103 | 2 | 99.297 | 1 |

`api_already_x5`는 API 값을 5로 나눠 1:5 문헌 밴드 척도에 맞춘 시나리오다. `measured`는 103지역이며 나머지는 기존 KNN 대체값이다.
