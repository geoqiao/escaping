# Your Issue-based personal site

**Preview:** [escaping-template](https://github.com/geoqiao/escaping-template) is where this
template is published. The 0.4.0 Action builds a live site on GitHub, but a repository made from
this template, including its step that creates the labels, has not been tried on GitHub yet.

## Start writing

1. Create your repository with **Use this template**. Name it `username.github.io`, or give it
   another name and the site lives at `username.github.io/<name>/`; a custom domain also works.
   On GitHub Free, keep it public. In **Settings → Pages**, set **Source: GitHub Actions**.
2. Write an Issue: a title and a Markdown body; image uploads work as usual.
3. Add exactly one of `type:blog`, `type:idea` or `type:about`, and `published` when it is ready.
   The workflow creates these labels on its first run; refresh the Issue page if you do not see
   them yet. The label change starts a build.

Remove `published` to take an Issue down on the next build. Closing an Issue does not unpublish
it. Without an About Issue, the About page shows your GitHub profile bio. Only Issues by the
repository owner (or `github.allowed_authors`) are published.

If one Issue has a problem, for example an invalid tag, the rest of the site is still published.
The run is marked failed, and its summary names the Issue and what to fix.

## Customize

`config.yaml` starts as `{}`; your repository and GitHub profile fill in the title, author, URL,
avatar and bio. Override what you like:

```yaml
site:
  title: My notes
  language: zh # Also switches the built-in Theme's interface text to Chinese.
theme:
  options:
    tagline: Writing about tools and learning
    featured_posts: [12, 7]
```

See the generator's [config.example.yaml](https://github.com/geoqiao/escaping/blob/main/config.example.yaml)
for every field. A mistyped field fails the build with a message that names it and suggests the
correct spelling.

To change the look, start with the built-in Theme's options. To change one part of it, create a
`theme/` directory with a `theme.yaml` containing `api: 4` and `extends: quiet`, add only the
template you want to replace, and set `theme: {use: ./theme}`. See the
[Theme guide](https://github.com/geoqiao/escaping/blob/main/docs/themes/authoring.md).

## Versions

The workflow runs the `escaping-site` package from PyPI at one version, `escaping-site@0.6.0`. To update,
change that number after reading the
[CHANGELOG](https://github.com/geoqiao/escaping/blob/main/CHANGELOG.md). Each job gets only the short-lived `GITHUB_TOKEN` permissions it needs; never put a token
in `config.yaml`. A failed build leaves the previously deployed site in place.

Bundled automation is MIT-licensed. Choose a license for your own writing separately.
