# mlmmj-docker
A docker image that runs the slim mailing list manager mlmmj.

**Important:** This image is under development right now, feel free to use it but be prepared that things may go wrong.

# About mlmmj
Mlmmj is a very simple but powerful mailing list manager (MLM). See the [Mlmmj homepage](http://mlmmj.org/) for more details.

# What is the Purpose of this Image?
This image installs mlmmj (built from source) and gives you an easy mailing list management.  There are some problems though on how to communicate with your mail delivery agent (like postfix). This image will help you to easily make mlmmj communicate with your postfix, but some changes are required, so you must be able to configure postfix (currently other MDAs are not supported).

# How to use this Image
I'll walk you through the process of how to get this image running. The idea was that mlmmj should be running in its own container s.t. postfix must not run in the container (wish would not be a good idea in terms of separation). I had the problem that my postfix does not (yet) run in docker but on the host. So I have not tested it with a postfix inside a docker container, but you should be able to extend and existing postfix image easily with this walkthrough s.t. it works with mlmmj. If you have any experience with that please let me know. I also intend to write my own postfix image and then will report my experience.

One note first: The current version of mlmmj is 1.3.0 (May 2017). There are also older versions available (different branches that correspond to the mlmmj versions). They're uploaded on duckerhub as well.

You must have a postfix running, either on your host machine or in another docker container. Usually mlmmj is added as a transport to postfix, so postfix runs the mlmmj-receive command. In the case the postfix runs in another container (or on your host) we can't execute this binary though. For this purpose I've written to python scripts that take care of this:

 - **mlmmj_listener.py** runs inside the container and gets started automatically. It listens on port 7777 and awaits instructions (mlmmj commands) that get executed in the container. Read the documentation at the beginning of the file for more information. Important note: Don't expose this port to the outside world, all commands it receives are executed and this could lead to dangerous situations. Expose it only in your docker network / on your localhost. Also it builds a path given the listname and does not check that path. That should be done by any software sending requests to the listener. For example a list name containing `.` or `..` seem evil. You should take care of such things when building a list (allow only a small set of reasonable charachters). Also the docs of mlmmj state that `-` should not be used in list names btw. But otherwise you should not worry about this script, its inside the container.
 - **postfix_incoming.py** is used on the machine where your postfix lives. Usually you tell postfix to call **mlmmj-receive** for the lists, since this lives in our container this script connects to the **mlmmj_listener.py** and calls mlmmj-receive inside the container. You have to place this script (on your host machine or a postfix image) and must be able to run it! It requires python 3.x and the python module requests (`pip install requests`).  Again it does not check any list names, you really should take care of that when creating lists.

So here's how to set it up, I hope I included all the steps I did (again, on my server not in any docker container). I tested it with Ubuntu 16.04.

 1. Postfix drops super user privileges and executes command as another user. So I decided to add a user `mlmmj` to the system. Quote from the mlmmj docs: "It usually makes sense to make this a  'system' user, with no password and no shell (/usr/false for the shell [...]"
 2.  Copy the file postfix_incoming.py in some directory where the mlmmj user can execute it. I put it in `/usr/local/sbin/` and make it executable (`chmod +x`).
 3. Edit your *postfix master.cf*, add the following pipe agent: `mlmmj   unix  -       n       n       -       -       pipe    flags=ORhu user=mlmmj argv=/usr/local/sbin/postfix_incoming.py --mlmmj localhost $nexthop`
 4.  Now it may be necessary to do some changes. With the `-mlmmj HOST` argument you can specify with which host the script will connect. In my case (follows later) I've exposed the port 7777 from postfix_incoming.py to my localhost. If this is some other host please adjust this (for example in a docker container this would be the linked mlmmj container).
 5. In your postfix *main.cf* make sure to add the following option (I think that's the default on Ubuntu at least): `recipient_delimiter = +`

Leave it for now, let's build the mlmmj container.
Here is my docker-compose file, hope that makes everything clear:
```yaml
version: "2"

services:
  mlmmj:
    image: fabianwe/mlmmj
    volumes:
      - ./mlmmj_conf:/mlmmj_conf
      - ./spool:/var/spool/mlmmj
    networks:
      mail-net:
        aliases:
          - mlmmj
    expose:
      - "7777"
    ports:
      - "127.0.0.1:7777:7777"

networks:
  mail-net:
    driver: bridge
```
Run `docker-compose up` and it should start working. In the ports section I exposed the port of the container to the localhost s.t. I can connect to localhost:7777 in order to reach the receiver script from my host.

Some important parts: I created a network called mail-net, you'll need the ip of that network (use `docker network ls` and search for it). Inspect the network with `docker network inspect NETWORKNAME`. Look for the "Subnet" part, for me it was `172.25.0.0/16`. If you don't use compose or create your own network look for the docker default net.

Now we have to tell postfix to accept connections from this network (mlmmj will use postfix to deliver the mail). In your *main.cf* add the network to your mynetworks, so I added `172.25.0.0/16`. Also there are two mounted volumes: *mlmmj_conf* and *spool*. The *mlmmj_conf* contains two files that are needed for postfix as well (so on your host or in your postfix container): *virtual* and *transport*. The spool directory contains all your mailing lists, in mlmmj this is typically */var/spool/mlmmj*. Now we must add these files to postfix: Edit your main.cf and adjust the following entries: `virtual_alias_maps = [...] hash:PATH_TO_MLMMJ_CONF/virtual` and `transport_maps = [...] hash:PATH_TO_MLMMJ_CONF/transport` where you have to replace `PATH_TO_MLMMJ_CONF` with the volume we just created. In a postfix container you would create a volume for that directory in your postfix container as well. Also add the following to *main.cf*: `mlmmj_destination_recipient_limit = 1`. Following the documentation of mlmmj you should also add `propagate_unmatched_extensions = virtual`.

Well that's that. Now some more notes on the docker image: By default it will connect with postfix on the machine running docker. It gets the IP of your machine with the command `/sbin/ip route|awk '/default/ { print $3 }'`. If you want to connect to a postfix running somewhere else pass the environment variable `POSTFIX_HOST` to the image and it will use this host instead (so usually a postfix image you link to mlmmj).

Now we're done and mlmmj is set up. You should have an empty *virtual* and *transport* file now in your *mlmmj_conf*. Create the postfix hash files for them by using `sudo postmap virtual` and `sudo postmap transport` in *mlmmj_conf*. Reload postfix (*postfix reload*).

Now everything should work, you can start creating your mailing lists. To do so follow the instructions from the mlmmj [README.postfix](http://mlmmj.org/docs/readme-postfix/). Run the commands inside your docker container with `exec`. They're all located under `/usr/local/bin`. So for example to create a mailing list use `docker-compose exec mlmmj /usr/local/bin/mlmmj-make-ml`.

After that you must modify your *transport* and *virtual* files as well as the alias file (usually */etc/aliases*) as described in the documentation. After that run `postmap` again for the *virtual* and *transport* file and run `sudo newaliases` and reload postfix. Of course you can also write a script that does this for you, I'm working on a nice web interface that can be linked to this mlmmj container and takes care of everything for you because the default usage is really a pain in the ass...

For your lists to work you must also change the relayhost for each list by hand (another pain in the ass I would like to avoid). In your list directory go to the control directory and add a file relayhost and add the IP of your postfix to it (in my case the IP under which my docker host machine is reachable). So add the value from `POSTFIX_HOST` to it. If you haven't specified this before the container on startup will print out this IP, for example: POSTFIX_HOST not specified, assuming that postfix is reachable on 172.19.0.1
The file *relayhost* will also be overwritten on each start of the mlmmj container, so you could also restart it and it should work as well.

Now start writing mails to your list and see what happens. It usually makes sense to inspect */var/log/mail.log* and watch the output of the mlmmj container, something should happen.

# Crontab
It is advised in the mlmmj documentation to use a crontab to run `mlmmj-maintd`. This image will do this every two hours.

# Changing the Language / Updating Text
Mlmmj uses various text (available in multiple languages) to send adminstration and information messages. However, these files are copied for each list inside the list directory (subdirectory text). So even if you update mlmmj to a new version you still have the old texts. Also changing the language of a list after creation requires you to copy the files around. Therefor I've written a small script that can be executed inside the container and does this job for you. Simply exec it: `docker-compose exec mlmmj /renew_text.sh LISTNAME LANGUAGE`. Without any arguments it will print some more details like:

```
Usage: /renew_text.sh LIST_NAME LANGUAGE
Available languages are:
ast  de  en  fi  fr  gr  it  pt  sk  zh-cn
```
This way you can update your texts to the newest version or another language.
# Open Questions / Bugs / TODOs
Well I haven't written mlmmj and there are some parts I still don't get 100%, even though I've read some parts of the code. On problem may be that we run the container as root (many of the mlmmj commands require this... and volumes often have permission problems...).
Problem: NOTE: The mailinglist directory (/var/spool/mlmmj/mlmmj-test in our  example) have to  be owned by the user the mailserver writes as. On some Postfix installations Postfix is run by the  user postfix, but still writes files as nobody:nogroup or nobody:nobody.

I don't know exactly what this means, does postfix write some files? Not sure...

If you have any problems feel free to contact me: fabianwen#posteo.eu (replace # with @ ...)
