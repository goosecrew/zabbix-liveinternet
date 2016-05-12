#!/usr/bin/python2.7
import requests
import sys
import png
import StringIO
import counter
import argparse
import subprocess

COLOR_WHITE = 0
COLOR_GRID = 2
COLOR_GRAY = 3
COLOR_GREEN = 4
COLOR_Y_AXIS = 1
COLOR_LW_GRID = 3
COLOR_LW_BACKGROUND = 1
COLOR_LW_AVG_7DAYS = 27
COLOR_LW_CURRENT = 11
COLOR_LW_YDAY = 19
COLOR_LW_AVG_THISDAY = 35


class Application:
    def __init__(self):
        self.args = self.parse_args()
        self.init_vars(mode=self.args.mode)
    def init_vars(self, mode):
        self.top_crop = 33
        # vychislyaetsya v prepare_matrix() isxodya iz polozheniya Y osi
        # self.left_crop = 48 if self.args.mode == 'last-day' else 52
        self.right_crop = 6 if self.args.mode == 'last-day' else 13
        self.bottom_crop = 60 if self.args.mode == 'last-day' else 98
        self.mv_crop_left = 0
        # vychislyaetsya v prepare_matrix() isxodya iz polozheniya Y osi
        # self.mv_crop_right = self.left_crop - 6
        self.mv_crop_top = self.top_crop - 12
        self.mv_crop_bottom = self.top_crop + 20 if self.args.mode == 'last-day' else self.top_crop+18
        self.login = 'http://{d}/'.format(d=self.args.domain)
        self.password = self.args.password
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 YaBrowser/16.3.0.7847 Safari/537.36"
        self.content_type = "application/x-www-form-urlencoded"
        self.content_length = 44
        self._accept = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        self.base_url = "http://www.liveinternet.ru"
        self.auth_url = "{b}/stat/".format(b=self.base_url)
        if mode == 'last-day':
            self.png_html_url = "{b}/stat/{d}/mins.html".format(b=self.base_url, d=self.args.domain)
        elif mode == 'last-week':
            self.png_html_url = "{b}/stat/{d}/online.html".format(b=self.base_url, d=self.args.domain)
        self.png_image_name_original = '{d}_{m}_live_internet_{m}.png'.format(d=self.args.domain, m=self.args.mode)
        self.png_image_name_cropped = '{d}_{m}_live_internet_cropped_{m}.png'.format(d=self.args.domain, m=self.args.mode)
        self.png_images_directory = '/tmp'

    def parse_args(self):
        p = argparse.ArgumentParser()
        p.add_argument('domain', choices='irr jobru ru'.split())
        p.add_argument('mode', choices='last-day last-week'.split())
        p.add_argument('action', choices='get-diff get-absolute'.split())
        p.add_argument('--debug', action='store_true')
        p.add_argument('--password', required=True)
        return p.parse_args()
    def connect(self):
        headers = {
            'content-type': self.content_type,
            'User-agent': self.user_agent,
            'content-length': self.content_length,
            'accept': self._accept
        }

        data = {
            "url": self.login,
            "password": self.password
        }

        http_req = requests.Request('POST', self.auth_url, headers=headers, data=data)
        http_prepared = http_req.prepare()
        http_session = requests.Session()
        http_session.send(http_prepared)
        return http_session
    def get_png_image_url(self, http_session, png_html_url, http_base_url, mode):
        if mode == 'last-day':
            pattern = '<img src="'
        elif mode == 'last-week':
            pattern = '<td><img src="'
        r = http_session.get(png_html_url)
        for line in r.text.split("\n"):
            if not pattern in line: continue
            return '{b}{u}'.format(
                b=http_base_url,
                u=line.split()[1].split('"')[1]
            )
    def get_png_binary_data(self, http_session, png_image_url):
        png_binary_data_response = http_session.get(png_image_url)
        return png_binary_data_response.content
    def get_png_io_object(self, png_binary_data):
        o = StringIO.StringIO()
        o.write(png_binary_data)
        o.seek(0)
        return o
    def get_png_instance(self, png_io_object):
        return png.Reader(file=png_io_object)
    def get_matrix_from_png(self, png_object):
        # konvertireum array.array => list, poluchaem matricu
        png_rows = [list(x) for x in list(png_object[2])]
        return png_rows
    def crop_matrix(self, matrix, crop_factor, negate=True):
        m = matrix
        f = crop_factor
        if negate:
            crop_factor['bottom'] = crop_factor['bottom'] * -1
            crop_factor['right'] = crop_factor['right'] * -1
        m = list(m[f['top']:f['bottom']])
        m = zip(*m)[f['left']:f['right']]
        m = zip(*m)
        return m
    def transpose_matrix(self, matrix):
        return zip(*matrix)
    def matrix_filter_grid_colors(self, matrix, grid_color):
        # ubiraem naxui setku - meshaet dlya rasschetov
        new_matrix = []
        for i in range(len(matrix)):
            new_row = []
            for j in range(len(matrix[i])):
                if j == 0 or j == len(matrix[i])-1:
                    new_value = matrix[i][j]
                elif matrix[i][j] != grid_color:
                    new_value = matrix[i][j]
                elif matrix[i][j-1] != matrix[i][j+1]:
                    new_value = matrix[i][j]
                else:
                    new_value = matrix[i][j-1]
                new_row.append(new_value)
            new_matrix.append(new_row)
        return new_matrix
    def replace_color(self, matrix, _from, _to):
        new_matrix = []
        for i in range(len(matrix)):
            new_row = []
            for j in range(len(matrix[i])):
                new_color = _to if matrix[i][j] == _from else matrix[i][j]
                new_row.append(new_color)
            new_matrix.append(new_row)
        return new_matrix
    def save_matrix_to_png(self, matrix, palette, bitdepth, file_name):
        width = len(matrix[0])
        height = len(matrix)
        png_writer = png.Writer(
            width = width ,
            height = height,
            bitdepth = bitdepth,
            palette = palette
        )

        png_writer.write(
            outfile=open('{d}/{n}'.format(d=self.png_images_directory,n=file_name),'wb'),
            rows=matrix
        )
    def get_last_row_index_for_a_color(self, matrix, color):
        m = matrix
        last_green_row_index = 0
        for i in range(len(m)):
            for j in range(len(m[i])):
                cv = m[i][j]
                if cv == color:
                    last_green_row_index = i
        return last_green_row_index
    def last_day_get_diff(self, matrix):
        m = matrix
        last_green_row_index = self.get_last_row_index_for_a_color(matrix=matrix, color=COLOR_GREEN)
        # check nachinaem tolko so vtoroi zelenoi strochki
        if last_green_row_index == 0:
            return 101
        # schitaem otklonenie ot vcherashnego dnya
        row_for_check = m[last_green_row_index-2]
        c = counter.Counter()
        for cv in row_for_check:
            if cv not in [COLOR_GREEN, COLOR_GRAY]: continue
            c[cv] += 1
        # esli serogo net - vse OK
        if c[COLOR_GRAY] == 0:
            return 102
        diff_pecrent =  min(100.0, 100-(float(c[COLOR_GRAY])/c[COLOR_GREEN])*100)
        if '--debug2' in sys.argv:
            print 'last green index ', last_green_row_index
            print 'total rows count', len(m)
            print 'counter is', dict(c.most_common())
            print 'diff ', diff_pecrent, '%'
        return diff_pecrent

    def last_day_get_absolute(self, matrix, y_max_value):
        m = matrix
        last_green_row_index = self.get_last_row_index_for_a_color(matrix=matrix, color=COLOR_GREEN)
        row_for_check = m[last_green_row_index-2]
        width = len(row_for_check)
        for i in range(len(row_for_check)):
            color = row_for_check[i]
            if color == COLOR_GREEN:
                first_index = i
                break
        green_widht = width - first_index
        percentage = float(green_widht)/width
        return y_max_value*percentage

    def last_week_get_absolute(self, matrix, y_max_value):
        m = matrix
        last_index = self.get_last_row_index_for_a_color(matrix=matrix, color=COLOR_LW_CURRENT)
        row_for_check = m[last_index-2]
        width = len(row_for_check)
        for i in range(len(row_for_check)):
            color = row_for_check[i]
            if color == COLOR_LW_CURRENT:
                first_index = i
                break
        cur_widht = width - first_index
        percentage = float(cur_widht)/width
        return y_max_value*percentage

    def last_week_get_diff(self, matrix):
        m = matrix

        last_index = self.get_last_row_index_for_a_color(matrix=m, color=COLOR_LW_CURRENT)
        row_for_check = m[last_index-2]
        width = len(row_for_check)
        for i in range(len(row_for_check)):
            color = row_for_check[i]
            if color == COLOR_LW_CURRENT:
                first_index = i
                break
        cur_width = width - first_index

        last_index = self.get_last_row_index_for_a_color(matrix=m, color=COLOR_LW_AVG_THISDAY)
        row_for_check = m[last_index-2]
        width = len(row_for_check)
        for i in range(len(row_for_check)):
            color = row_for_check[i]
            if color == COLOR_LW_AVG_THISDAY:
                first_index = i
                break
        weekago_width = width - first_index

        diff_pecrent =  min(100.0, 100-(float(weekago_width)/cur_width)*100)
        return diff_pecrent
    def parse_y_max_value_from_png(self, file_name):
        p = subprocess.Popen(
            'gocr -C "0123456789,." -i {p}/{n}'.format(p=self.png_images_directory,n=file_name).split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        o,e = p.communicate()
        s = o.strip().replace('O','0').replace('.','').replace(',','')
        return int(s)

    def get_counter_of_colors(self, matrix):
        c = counter.Counter()
        for row in matrix:
            for cell_value in row:
                c[cell_value] += 1
        print c.most_common(100)

    def find_y_axis_left(self, original_matrix):
        # ischem v 50 stroke matrici...
        for j in range(len(original_matrix[50])):
            # pervyi chernyi pixel...
            if original_matrix[50][j] != COLOR_Y_AXIS: continue
            return j

    def set_crops(self, y_axis_leftpos):
        # dlya max-value idem vlevo, vychitaem BbICTYn metok po Y osi (minus 3) i eshe 2 pixela vlevo
        # _right - potomu chto otrezaem vse chto praveee
        self.mv_crop_right = y_axis_leftpos-3-2
        # dlya grafika yaoborot idem vpravo na 3 pixela
        # _left - potomu chto otrezaem vse chto levee
        self.left_crop = y_axis_leftpos+3

    def prepare_matrix(self, http_session):
        png_image_url = self.get_png_image_url(
            http_session=http_session,
            png_html_url=self.png_html_url,
            http_base_url=self.base_url,
            mode=self.args.mode
        )
        png_binary_data = self.get_png_binary_data(
            http_session=http_session,
            png_image_url=png_image_url
        )
        png_io_object = self.get_png_io_object(
            png_binary_data=png_binary_data
        )
        png_instance = self.get_png_instance(
            png_io_object=png_io_object
        )
        png_object = png_instance.read()
        palette = png_object[3]['palette']
        bitdepth = png_object[3]['bitdepth']
        matrix = self.get_matrix_from_png(png_object=png_object)
        # matrix = self.replace_color(matrix=matrix, _from=35, _to=COLOR_LW_BACKGROUND)
        self.save_matrix_to_png(matrix=matrix, palette=palette, bitdepth=bitdepth, file_name=self.png_image_name_original)
        self.set_crops(y_axis_leftpos=self.find_y_axis_left(original_matrix=matrix))
        grid_color = COLOR_GRID if self.args.mode == 'last-day' else COLOR_LW_GRID
        matrix = self.matrix_filter_grid_colors(matrix=matrix, grid_color=grid_color)
        main_crop_factor = {
            'top':self.top_crop,
            'bottom':self.bottom_crop,
            'left':self.left_crop,
            'right':self.right_crop
        }
        mv_crop_factor = {
            'top':self.mv_crop_top,
            'bottom':self.mv_crop_bottom,
            'left':self.mv_crop_left,
            'right':self.mv_crop_right
        }
        main_cropped_matrix = self.crop_matrix(matrix=matrix, crop_factor=main_crop_factor)
        main_cropped_matrix = self.transpose_matrix(matrix=main_cropped_matrix)
        self.save_matrix_to_png(
            matrix=main_cropped_matrix,
            palette=palette,
            bitdepth=bitdepth,
            file_name=self.png_image_name_cropped
        )
        mv_cropped_matrix = self.crop_matrix(matrix=matrix, crop_factor=mv_crop_factor, negate=False)
        mv_file_name='mv_{n}'.format(n=self.png_image_name_cropped,d=self.args.domain,m=self.args.mode)
        self.save_matrix_to_png(
            matrix=mv_cropped_matrix,
            palette=palette,
            bitdepth=bitdepth,
            file_name=mv_file_name
        )
        self.y_max_value = self.parse_y_max_value_from_png(file_name=mv_file_name)
        return main_cropped_matrix

    def mode_last_day(self, matrix):
        if self.args.action == 'get-diff':
            return self.last_day_get_diff(matrix=matrix)
        elif self.args.action == 'get-absolute':
            return self.last_day_get_absolute(matrix=matrix, y_max_value=self.y_max_value)

    def mode_last_week(self, matrix):
        if self.args.action == 'get-diff':
            return self.last_week_get_diff(matrix=matrix)
        elif self.args.action == 'get-absolute':
            return self.last_week_get_absolute(matrix=matrix, y_max_value=self.y_max_value)

    def run(self):
        matrix = self.prepare_matrix(http_session=self.connect())
        if self.args.mode == 'last-day':
            print self.mode_last_day(matrix=matrix)
        elif self.args.mode == 'last-week':
            print self.mode_last_week(matrix=matrix)


try:
    Application().run()
except Exception as e:
    if '--debug' in sys.argv:
        import traceback
        print traceback.format_exc()
    else:
        print -1
    sys.exit(1)
