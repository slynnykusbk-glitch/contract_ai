# Developer Notes

## Force-enable comments

In some Word environments the `WordApi 1.4` requirement set is reported as unsupported even though `Word.Comment` is available.
To force-enable comments for testing, run the following in the browser console and reload the add-in:

```js
localStorage.setItem('cai.force.comments', '1');
```

Remove the key or set it to another value to disable the override.
