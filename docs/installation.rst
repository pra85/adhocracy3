Installation
==============

Installation
------------

Requirements (Tested on Debian\Ubuntu,  64-Bit is mandatory):

1. git
2. python python-setuptools python-docutils
3. build-essential libssl-dev libbz2-dev libyaml-dev libncurses5-dev
4. graphviz
5. ruby ruby-dev
6. gettext

If you don't use the custom compiled python (see below) you need some
some basic dependencies to build PIL (python image library):

6. libjpeg8-dev zlib1g-dev (http://pillow.readthedocs.org/en/latest/installation.html)

Create SSH key and upload to GitHub ::

    ssh-keygen -t rsa -C "your_email@example.com"

Checkout source code ::

    git clone git@github.com:liqd/adhocracy3.git
    cd adhocracy3
    git submodule update --init

Create virtualenv ::

    virtualenv -p python3.4 .

If you don't have python 3.4 on your system, you may compile python 3.4 and
Pillow instead of creating a virtualenv ::

    cd python
    python ./bootstrap.py
    ./bin/buildout
    ./bin/install-links
    cd ..

Install adhocracy ::

    ./bin/python ./bootstrap.py --buildout-version 2.4.4 --setuptools-version=18.3.2
    ./bin/buildout

Update your shell environment::

    source ./source_env


Documentation
-------------

Build sphinx documentation ::

    bin/sphinx_build_adhocracy
    xdg-open docs/build/html/index.html  # (alternatively, cut & paste the url into your browser)


Run the application
-------------------

Start supervisor (which manages the ZODB database, the Pyramid application
and the Autobahn websocket server)::

    ./bin/supervisord
    ./bin/supervisorctl start adhocracy:*

Check that everything is running smoothly::

    ./bin/supervisorctl status

Get information about the current workflow::

  ./bin/set_workflow_state --info etc/development.ini <path-to-process>
  # Example
  ./bin/set_workflow_state --info etc/development.ini /mercator

Change the workflow state (most actions are not allowed for a normal user in the initial 'draft' state)::

  ./bin/set_workflow_state etc/development.ini <path-to-process> <states-to-transition>
  # Example
  ./bin/set_workflow_state etc/development.ini /mercator announce participate

Open the javascript front-end with your web browser::

    xdg-open http://localhost:6551/

Shutdown everything nicely::

    ./bin/supervisorctl shutdown


Run test suites
---------------

Run test suite::

    bin/polytester

.. NOTE:: You need to have chrome/chromium installed in order to run the
   acceptance tests.


Troubleshooting
---------------
If you encounter this error when starting adhocracy

    Problem connecting to WebSocket server: ConnectionRefusedError: [Errno 111] Connection refused

delete the `var/WS_SERVER.pid` file and retry again. This happens when
the Websocket server is not shutdown properly.
