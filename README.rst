Adhocracy 3 with customizations for various projects
====================================================

.. image:: https://api.travis-ci.org/liqd/adhocracy3.png?branch=master
    :target: http://travis-ci.org/liqd/adhocracy3
.. image:: https://coveralls.io/repos/liqd/adhocracy3/badge.png?branch=master
    :target: https://coveralls.io/r/liqd/adhocracy3
.. image:: https://readthedocs.org/projects/adhocracy3/badge/?version=latest
    :target: https://adhocracy3.readthedocs.org/

This repository contains the source code of the Adhocracy 3 backend and
frontend cores as well as customizations for various projects.

Note::

    This isn't meant for general consumption at this stage. Many expected
    things do not work yet!

This project (i.e. all files in this repository if not declared otherwise) is
licensed under the GNU Affero General Public License (AGPLv3), see
LICENSE.txt.


Further reading :doc:`installation`


Softwarestack
-------------

Server (backend):

- `Python 3 <https://www.python.org>`_ (programming language)

- `Pyramid <http://pylonsproject.org>`_  (web framework)

- `substance D <http://docs.pylonsproject.org/projects/substanced/en/latest>`_ (application framework/server)

- `hypatia <https://github.com/Pylons/hypatia>`_ (search)

- `ZODB <http://zodb.org>`_ (database)

- `colander <http://docs.pylonsproject.org/projects/colander/en/latest/>`_ (data schema)

- `Autobahn|Python <http://autobahn.ws/python/>`_ (websocket servers)

- `websocket-client <https://github.com/liris/websocket-client>`_ (websocket
  client)

- `buildout <http://www.buildout.org/en/latest/>`_ (build system)


Client (frontend):

- `JavaScript <https://developer.mozilla.org/en-US/docs/Web/JavaScript>`_ (programming language)

- `TypeScript <http://www.typescriptlang.org/>`_ (programming language)

- `RequireJS <http://requirejs.org/>`_ (module system)

- `AngularJS <http://angularjs.org/>`_ (application framework)

- `JQuery <https://jquery.com/>`_ (javascript helper library)

- `Lodash <https://lodash.com/>`_ (functional javascript helper library)

- `Protractor <https://angular.github.io/protractor/>`_ (acceptance tests)

- `Jasmine <https://jasmine.github.io/>`_ (unit tests)

- `Sass <http://sass-lang.com/>`_/`Compass <http://compass-style.org/>`_
  (CSS preprocessor)

- `Grunt <http://gruntjs.com/>`_ (build system)
