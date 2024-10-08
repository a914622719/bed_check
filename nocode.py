import sys
import execjs
import feapder
import argparse
import requests
import atexit

from env import *
from feapder.utils.log import log

global bark_log


class CQ(feapder.AirSpider):
    class InfoError(Exception):
        def __init__(self, *args, **kwargs):  # real signature unknown
            pass

    class CodeError(Exception):
        def __init__(self, *args, code='', code_result='', **kwargs):  # real signature unknown
            self.code = code
            self.code_result = code_result

    def start_requests(self):
        log.info("开始执行")
        global bark_log
        bark_log = bark_log + f"用户名：{USERNAME}\n"
        log.info(f"用户名：{USERNAME}")
        self.send_msg("开始执行", level="INFO")
        login_url = "https://ids.gzist.edu.cn/lyuapServer/v1/tickets"
        post_data = {
            "username": USERNAME,
            "password": self.encrypt_password(PASSWORD),
            "service": "https://xsfw.gzist.edu.cn/xsfw/sys/swmzncqapp/*default/index.do"
        }
        login_response = feapder.Request(url=login_url, data=post_data).get_response().json
        try:
            params = {"ticket": login_response["ticket"]}
        except KeyError:
            data_code = login_response["data"]["code"]
            if data_code == 'NOUSER':
                bark_log = bark_log + "用户名错误\n"
                raise self.InfoError(fr"用户名错误")
            elif data_code == 'PASSERROR':
                bark_log = bark_log + "密码错误\n"
                raise self.InfoError(fr"密码错误")
            elif data_code == 'ISMODIFYPASS':
                bark_log = bark_log + "密码未修改\n"
                raise self.InfoError(fr"密码未修改")
            elif data_code == 'ISPHONEOREMAILORANSWER':
                bark_log = bark_log + "未绑定手机或邮箱或密保问题\n"
                raise self.InfoError(fr"未绑定手机或邮箱或密保问题")
            raise KeyError(fr"返回值未知,尝试重新运行: {data_code}")
        except Exception as e:
            bark_log = bark_log + fr"发生未知错误,尝试重新运行: {e}\n"
            raise Exception(fr"发生未知错误,尝试重新运行: {e}")
        jump_url = "https://xsfw.gzist.edu.cn/xsfw/sys/swmzncqapp/*default/index.do"
        yield feapder.Request(
            url=jump_url,
            callback=self.parse_getSelRoleConfig,
            params=params)

    def parse_getSelRoleConfig(self, request, response):
        url = "https://xsfw.gzist.edu.cn/xsfw/sys/swpubapp/MobileCommon/getSelRoleConfig.do"
        cookies = response.cookies
        json = {
            "APPID": "5405362541914944",
            "APPNAME": "swmzncqapp"
        }
        yield feapder.Request(
            url,
            callback=self.parse_done,
            cookies=cookies,
            json=json)

    def parse_done(self, request, response):
        url = "https://xsfw.gzist.edu.cn/xsfw/sys/swmzncqapp/modules/studentCheckController/uniFormSignUp.do"
        cookies = response.cookies
        yield feapder.Request(
            url,
            callback=self.parse,
            cookies=cookies)

    def parse(self, request, response):
        global bark_log
        try:
            result = response.json["msg"]
            if result == ' 当前时段不在考勤时段内':
                bark_log = bark_log + f"::warning:: {result}\n"
                log.warning(f"::warning:: {result}")
                self.send_msg(result, "INFO")
                return
            elif result == ' 您已签到,请勿重复签到':
                pass
            log.info(fr"查寝结果：{result}")
            bark_log = bark_log + fr"查寝结果：{result} " + "\n"
            self.send_msg(result, "INFO")
        except Exception as e:
            bark_log = bark_log + f"::error:: 查寝失败，结果未知：{e}\n"
            log.error(f"::error:: 查寝失败，结果未知：{e}")

    def exception_request(self, request, response, e: Exception):
        global bark_log
        if type(e) is self.InfoError:
            self.send_msg(f"{e}", "ERROR")
            self.stop_spider()
            tools.delay_time(1)
        elif type(e) is KeyError:
            bark_log = bark_log + f"返回值未知：{e}\n"
            self.send_msg(f"返回值未知：{e}", "ERROR")
        elif type(e) is Exception:
            bark_log = bark_log + f"发生未知错误：{e}\n"
            self.send_msg(f"发生未知错误：{e}", "ERROR")

        log.error(f"::error:: {e}")

    @staticmethod
    def send_msg(msg, level="DEBUG", message_prefix=""):
        msg = f"{USERNAME}\n{msg}"
        tools.send_msg(msg, level=level, message_prefix=message_prefix)

    @staticmethod
    def js_from_file(file_name):
        """
        读取js文件
        :return:
        """
        with open(file_name, 'r', encoding='UTF-8') as file:
            result = file.read()
        return result

    def encrypt_password(self, password):
        # 编译加载js字符串
        context1 = execjs.compile(self.js_from_file('./login.js'))
        encrypted_password = context1.call("encrypt", password)
        return encrypted_password


def get_username_password_from_env():
    username = os.environ.get("LOGIN_USERNAME")
    password = os.environ.get("LOGIN_PASSWORD")
    global bark_log
    bark_log = os.environ.get("BARK_URL")

    return username, password


def get_username_password_from_config(config_file, section):
    config = configparser.ConfigParser()
    config.read(config_file)
    if config.has_section(section):
        username = config.get(section, 'LOGIN_USERNAME')
        password = config.get(section, 'LOGIN_PASSWORD')
        return username, password
    else:
        return None, None


def get_username_password_manually():
    username = input("请输入用户名: ")
    password = input("请输入密码: ")
    return username, password


def get_username_password():
    parser = argparse.ArgumentParser(description='获取用户名和密码')
    parser.add_argument('-e', '--env', action='store_true', help='从环境变量中获取用户名和密码')
    parser.add_argument('-c', '--config', type=str, help='读取配置文件获取用户名和密码')
    parser.add_argument('-u', '--username', type=str, help='命令行输入用户名')
    parser.add_argument('-p', '--password', type=str, help='命令行输入密码')
    args = parser.parse_args()

    if args.env:
        set_setting_from_env()
        return get_username_password_from_env()
    elif args.config:
        set_setting_from_config(args.config, "setting")
        return get_username_password_from_config(args.config, 'loginInfo')
    elif args.username and args.password:
        return args.username, args.password
    else:
        return get_username_password_manually()


def exit_handler():
    # 在这里编写程序退出前需要执行的操作
    log.info("发送通知：" + bark_log)
    requests.get(bark_log)
    # 保存数据、关闭连接或者清理资源等


if __name__ == '__main__':
    atexit.register(exit_handler)
    USERNAME, PASSWORD = get_username_password()
    global bark_log
    if USERNAME and PASSWORD:
        CQ().start()
    else:
        if not USERNAME:
            bark_log = bark_log + "::error:: 账号不能为空\n"
            log.error("::error:: 账号不能为空")
            requests.get(bark_log)
            sys.exit(1)

        if not PASSWORD:
            bark_log = bark_log + "::error:: 密码不能为空\n"
            log.error("::error:: 密码不能为空")
            requests.get(bark_log)
            sys.exit(1)
