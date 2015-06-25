# api-latency-experiments

## Experiment 1

Step 1.

Hits these URLs repeatedly:

'WWW.FT.COM':
    http://www.ft.com/home/uk
'API-V2':
    http://api.ft.com/content/notifications?since=%s
'API-V1':
    http://api.ft.com/content/notifications/v1/items?since=%s
'NEXT.FT.COM':
    http://next.ft.com/uk
'WWW.FT.COM-RSS':
    http://www.ft.com/rss/home/uk
'APP.FT.COM':
    http://app.ft.com/api/v1/structure/v7?edition=dynamic&region=uk&icb=23887251&contenttype=magazine
'FASTFT':
    http://clamo.ftdata.co.uk/api?request=%5B%7B%22action%22%3A%22search%22%2C%22arguments%22%3A%7B%22query%22%3A%22%22%2C%22limit%22%3A5%2C%22offset%22%3A0%2C%22outputfields%22%3A%7B%22id%22%3Atrue%2C%22title%22%3Atrue%2C%22content%22%3A%22html%22%2C%22abstract%22%3A%22html%22%2C%22datepublished%22%3Atrue%2C%22shorturl%22%3Atrue%2C%22metadata%22%3Atrue%2C%22tags%22%3A%22visibleonly%22%2C%22authorpseudonym%22%3Atrue%2C%22attachments%22%3A%22html%22%2C%22slug%22%3Atrue%7D%7D%7D%5D

- Writes [request time,endpoint,uuid], for each UUID found in response that wasn't in the previous response from that endpoint

Step 2.

Throws UUIDs at API to find out
- source (METHODE, BLOGS, FASTFT, UNKNOWN)
- publishedDate

Writes [uuid,endpoint,source,(appearance time - published_date),title]

Step 3.

Finds the first appearance of each uuid and fills time buckets based on the appearance interval

Writes [time-bucket,*method-percentage], method-percentage being the % of items in each method that had appeared by the end of that time bucket



