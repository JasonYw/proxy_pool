import smtplib
import os
import configparser

abspath = os.path.abspath(__file__).replace(f"/{os.path.basename(__file__)}", "")
config = configparser.ConfigParser()
config.read(f"{abspath}/conf.ini")
EMAIL_HOST_USER = config["EMAIL"]["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = config["EMAIL"]["EMAIL_HOST_PASSWORD"]
EMAIL_PORT = config["EMAIL"]["EMAIL_PORT"]
EMAIL_HOST = config["EMAIL"]["EMAIL_HOST"]


def send_mail(subject, message, receivers=[EMAIL_HOST_USER]):
    try:
        msg = "Subject: {}\n\n{}".format(subject, message)
        server = smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT)
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.sendmail(EMAIL_HOST_USER, receivers, msg)
    except Exception as e:
        raise e
    finally:
        server.quit()


if __name__ == "__main__":
    pass
