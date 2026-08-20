# Inside-joke template

Add an object to the `"speak"` array in `custom.json`, then replace every
`YOUR_…` value. Restart the bot after saving.

```json
{
  "text": "Vaporeon has heard about YOUR_INSIDE_JOKE and is taking it very seriously.",
  "category": "YOUR_UNIQUE_MOOD",
  "rarity": "common",
  "quote": false,
  "tags": ["inside_joke", "YOUR_FRIEND_OR_TOPIC"]
}
```

Example after filling it in:

```json
{
  "text": "Vaporeon has declared the blue couch to be sovereign territory.",
  "category": "blue_couch",
  "rarity": "rare",
  "tags": ["inside_joke", "blue_couch"]
}
```

Use `common` for a normal chance, `rare` for an occasional surprise, or
`legendary` for an event-level line. If you set a unique category, such as
`blue_couch`, you can call it directly with `/vaporeon-speak mood:blue_couch`.

`quote` is optional and defaults to `true`. Set `"quote": false` when the
inside joke already has its own punctuation or should appear as a direct bot
announcement instead of as quoted dialogue.
