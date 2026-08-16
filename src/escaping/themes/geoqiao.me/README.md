# geoqiao.me Theme

The default built-in Theme is a Chinese-first personal writer system built around
Geo Qiao's magenta-and-mint gestural `GQ` mark. It uses local system fonts,
neutral light and deep-plum dark surfaces, restrained motion, and no remote
Webfont dependency. First visit follows the operating-system color scheme; an
explicit visitor choice is stored locally.

Home dedicates the first viewport to the newest Blog entry and the author mark.
The following section lists up to four more posts as borderless editorial rows.
Profile and About copy stay off Home; About remains its own long-form page, and
Blog archive pages own pagination.

Blog, Ideas, and Tag archives share the same editorial index grammar without a
card grid or dense dividers. Blog and Idea details use a 720px reading column,
immutable Issue metadata, and a desktop section outline that collapses on small
screens. Projects use numbered work rows, Tags use a subject matrix, and About
uses the same reading and author-mark language.

The Theme renders the complete strict SiteModel: Home, Blog archive/detail and
pagination, Ideas, About, Projects, and Tags. `_comments.html` owns only the
comments container and Theme default; the generator-owned shared `comments.js`
provides immutable Issue-number binding, automatic Theme synchronization,
message validation, and the Safari lazy-iframe workaround.
