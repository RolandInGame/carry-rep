# Privacy

CarryRep is a Discord bot that records reviews of game boosters so their reputation can be checked across servers. Each running instance serves one game.

## What is stored

- **Boosters who run `/register`:** Discord user ID and username, and what they type in the form (services, platform/region, where to find them, notes).
- **Reviews:** reviewer's Discord user ID, the booster's Discord user ID, rating, comment, the ID of the server where the review was written, and timestamps.
- **Usage events:** which command or button was used, by which Discord user ID, in which server. Used only to count activity.
- **Servers:** ID, name and member count of servers where the bot is installed.

The bot does not read messages, member lists or presence, and does not send direct messages.

## Who can see it

- A registered booster's card (services, platform, contact info, rating, number of servers, recent 4–5 star comments with the reviewer's mention) is shown to anyone who looks them up.
- 4–5 star reviews are posted in the channel where they are written. 1–3 star reviews are not posted and are not quoted; they only count in the average.
- Only people who registered as boosters can be looked up or reviewed.
- Data is not sold or shared with third parties.

## Deleting your data

Run `/deletemydata` (or press **Delete my data** on a panel). It deletes your booster registration, all reviews you received, all reviews you gave, and your usage events. Daily database backups are kept for up to 14 days and then removed.

## Contact

Open an issue in this project's repository.
