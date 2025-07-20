import logging
import os
import sys
from constants import REMOVAL_MESSAGE_SUBJECT, REMOVAL_COMMENT, REMOVAL_MESSAGE

import praw

SUBREDDIT_NAME = os.environ["SUB_NAME"]
INCHES_ON_PAGE = 8.5  # A Letter (ANSI A) sized paper is 8.5 inches wide
MIN_IMAGE_WIDTH_PIXELS = 1650  # Subreddit's threshold width. 1650/8.5 ~= 194 dots per inch (DPI)
NUM_POSTS_TO_PROCESS = 10


def setup_logger() -> None:
    logging.basicConfig(
        format="[%(asctime)s] %(message)s",
        datefmt="%m-%d %I:%M",
        level=logging.INFO,
        handlers=[
            logging.FileHandler("logs.txt", mode="a"),
            logging.StreamHandler(),
        ],
    )


def create_reddit_instance() -> praw.Reddit:
    try:
        reddit = praw.Reddit(
            username=os.environ["USERNAME"],
            password=os.environ["PASSWORD"],
            client_id=os.environ["CLIENT_ID"],
            client_secret=os.environ["CLIENT_SECRET"],
            user_agent=os.environ["USER_AGENT"],
            ratelimit_seconds=600,
        )

    except Exception as e:
        logging.error("Failed to authenticate: %s", e)
        sys.exit()

    return reddit


def extract_image_width_from_bodytext(selftext: str) -> int:
    try:
        extracted_string = selftext.split("width=")[1].split("&")[0]
        width = int(extracted_string)
        return width

    except IndexError:
        return -1


def calculate_image_dpi(image_width: int) -> int:
    return round(image_width / INCHES_ON_PAGE)


def reject_submission(submission: praw.models.Submission, image_width: int) -> None:
    dpi_value = calculate_image_dpi(image_width)
    submission.mod.remove(spam=False)
    submission.mod.flair(
        text="Post Removed: Low Quality Image",
        css_class="removed",
        flair_template_id="7e1d0b6c-b178-11ee-866f-b61c7ef1fdc8",
    )
    submission.mod.lock()
    removal_comment_with_author = REMOVAL_COMMENT.format(
        author=submission.author, sub=SUBREDDIT_NAME, dpi=dpi_value
    )
    removal_message_with_subreddit_name = REMOVAL_MESSAGE.format(
        sub=SUBREDDIT_NAME, dpi=dpi_value
    )
    submission.mod.send_removal_message(
        type="public_as_subreddit",
        message=removal_comment_with_author,
    )
    submission.mod.send_removal_message(
        type="private",
        title=REMOVAL_MESSAGE_SUBJECT,
        message=removal_message_with_subreddit_name,
    )
    logging.info("REJECT, %s, %d, %s", submission.id, image_width, submission.author)


def approve_submission(submission: praw.models.Submission, image_width: int) -> None:
    submission.mod.approve()
    logging.info("APPROVE, %s, %d, %s", submission.id, image_width, submission.author)


def process_submission(submission: praw.models.Submission) -> None:
    if submission.approved:
        return

    if submission.link_flair_text in {"Question", "Success Story!", "Meta"}:
        return

    image_width = extract_image_width_from_bodytext(submission.selftext)

    if image_width == -1:
        logging.error(
            "UNABLE TO EXTRACT WIDTH FROM BODY TEXT, %s, %s",
            submission.id,
            submission.author,
        )

    elif image_width < MIN_IMAGE_WIDTH_PIXELS:
        reject_submission(submission, image_width)

    else:
        approve_submission(submission, image_width)


if __name__ == "__main__":
    setup_logger()
    reddit = create_reddit_instance()
    subreddit = reddit.subreddit(SUBREDDIT_NAME)

    for submission in subreddit.new(limit=NUM_POSTS_TO_PROCESS):
        process_submission(submission)
