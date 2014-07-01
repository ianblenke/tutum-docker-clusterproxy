tutum-docker-clusterproxy
=========================

HAproxy image that balances between linked containers and, if launched in Tutum, 
reconfigures itself when a linked cluster member joins or leaves


Usage
-----

Make sure your application container exposes port 80. Then, launch it:

	docker run -d --name web1 tutum/hello-world
	docker run -d --name web2 tutum/hello-world

Then, run tutum/haproxy-http linking it to the target containers:

	docker run -d -p 80:80 --link web1:web1 --link web2:web2 tutum/haproxy


Configuration
-------------

You can overwrite the following HAproxy configuration options:

* `PORT` (default: `80`): Port HAproxy will bind to, and the port that will forward requests to.
* `MODE` (default: `http`): Mode of load balancing for HAproxy. Possible values include: `http`, `tcp`, `health`.
* `BALANCE` (default: `roundrobin`): Load balancing algorithm to use. Possible values include: `roundrobin`, `static-rr`, `source`, `leastconn`.
* `SSL_CERT` (default:  `**None**`): An optional certificate to use on the binded port. It should have both the private and public keys content. If using it for HTTPS, remember to also set `PORT=443` as the port is not changed by this setting.
Check [the HAproxy configuration manual](http://haproxy.1wt.eu/download/1.4/doc/configuration.txt) for more information on the above.


Usage within Tutum
------------------

Launch your applicaiton within Tutum's web interface.

Then, launch another application with tutum/haproxy which is linked to the application cluster created earlier, and with "Full Access" API role (or other appropiate read-only role).

That's it - the proxy container will start querying Tutum's API for an updated list of application cluster members and reconfigure itself automatically.
