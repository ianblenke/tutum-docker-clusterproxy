tutum-docker-clusterproxy
=========================

HAproxy image that balances between linked containers and, if launched in Tutum, 
reconfigures itself when a linked cluster member joins or leaves


Usage
-----

Make sure your application container exposes port 80. Then, launch it:

	docker run -d -p 8000:80 --name web1 tutum/hello-world
	docker run -d -p 8001:80 --name web2 tutum/hello-world

Then, run tutum/haproxy-http linking it to the target containers:

	docker run -d -p 80:80 --link web1:web1 --link web2:web2 tutum/haproxy-http


Usage within Tutum
------------------

Make sure your application container exposes port 80, and launch it within Tutum's web interface in a cluster.

Then, launch a container (or a cluster) with tutum/haproxy-http which is linked to the application cluster created earlier, and with "Full Access" API role (or other appropiate read-only role).

That's it - the proxy container will start querying Tutum's API for an updated list of application cluster members and reconfigure itself automatically.
