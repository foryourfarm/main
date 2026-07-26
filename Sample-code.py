import requests

url = 'http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList'
params ={'serviceKey' : '서비스키', 'Page_Size' : '10', 'Page_No' : '1', 'Obsr_Spot_Nm' : '구례군 구례읍', 'Obsr_Spot_Code' : '542805A001', 'Do_Se_Code' : '5', 'Mgc_Code' : '74', 'Obsr_Begin_Datetm' : '2016-05-04 ' }

response = requests.get(url, params=params)
print(response.content)