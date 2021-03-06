from tensorflow.python import keras
from tensorflow.python.keras.callbacks import TensorBoard
import tensorflow.python as tf
from train import create_model, get_anchors, get_classes, create_dataset
from tensorflow import py_function
from yolo3.model import preprocess_true_boxes, yolo_body, tiny_yolo_body, yolo_loss, mobile_yolo_body
from yolo3.utils import get_random_data
from keras_mobilenet import MobileNet
import numpy as np
import matplotlib.pyplot as plt
import cv2


def test_model_graph():
    """ tensorflow.keras 中load weights不支持那个跳过不匹配的层，所以必须手动控制权重 """
    yolo = keras.models.load_model('model_data/yolo_weights.h5')  # type:keras.models.Model
    tbcback = TensorBoard()
    tbcback.set_model(yolo)

    annotation_path = 'train.txt'
    log_dir = 'logs/000/'
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)

    input_shape = (416, 416)  # multiple of 32, hw

    h, w = input_shape
    image_input = keras.Input(shape=(h, w, 3))
    num_anchors = len(anchors)

    y_true = [keras.Input(shape=(h // {0: 32, 1: 16, 2: 8}[l], w // {0: 32, 1: 16, 2: 8}[l],
                                 num_anchors // 3, num_classes + 5)) for l in range(3)]

    model_body = yolo_body(image_input, num_anchors // 3, num_classes)
    print('Create YOLOv3 model with {} anchors and {} classes.'.format(num_anchors, num_classes))

    yolo_weight = yolo.get_weights()
    for i, w in enumerate(yolo_weight):
        if w.shape == (1, 1, 1024, 255):
            yolo_weight[i] = w[..., :(num_anchors // 3) * (num_classes + 5)]
        if w.shape == (1, 1, 512, 255):
            yolo_weight[i] = w[..., :(num_anchors // 3) * (num_classes + 5)]
        if w.shape == (1, 1, 256, 255):
            yolo_weight[i] = w[..., :(num_anchors // 3) * (num_classes + 5)]
        if w.shape == (255,):
            yolo_weight[i] = w[:(num_anchors // 3) * (num_classes + 5)]
    model_body.set_weights(yolo_weight)


def test_dict_dataset():
    """ 尝试输出字典形式的dataset """
    annotation_path = 'train.txt'
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)

    val_split = 0.1
    with open(annotation_path) as f:
        annotation_lines = f.readlines()
    np.random.seed(10101)
    np.random.shuffle(annotation_lines)
    np.random.seed(None)
    num_val = int(len(annotation_lines) * val_split)
    num_train = len(annotation_lines) - num_val

    batch_size = 32
    input_shape = (416, 416)

    num = len(annotation_lines)
    if num == 0 or batch_size <= 0:
        raise ValueError

    def parser(lines):
        image_data = []
        box_data = []
        for line in lines:
            image, box = get_random_data(line, input_shape, random=True)
            image_data.append(image)
            box_data.append(box)
        image_data = np.array(image_data)
        box_data = np.array(box_data)
        y_true = preprocess_true_boxes(box_data, input_shape, anchors, num_classes)
        return {'input_1': image_data, 'input_2': y_true[0], 'input_3': y_true[1], 'input_4': y_true[2]}

    # x_set = (tf.data.Dataset.from_tensor_slices(annotation_lines).
    #          apply(tf.data.experimental.shuffle_and_repeat(batch_size * 300, seed=66)).
    #          batch(batch_size, drop_remainder=True).
    #          map(lambda lines: py_function(parser, [lines], ({'input_1': tf.float32, 'input_2': tf.float32, 'input_3': tf.float32, 'input_4': tf.float32}))))
    # y_set = tf.data.Dataset.from_tensors(tf.zeros(batch_size, tf.float32)).repeat()
    # dataset = tf.data.Dataset.zip((x_set, y_set))
    # dataset_iter = dataset.make_one_shot_iterator()
    # dataset_iter.get_next()


def test_parser():
    """ 测试parser函数以支持eager tensor """
    annotation_path = 'train.txt'
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)

    val_split = 0.1
    with open(annotation_path) as f:
        annotation_lines = f.readlines()
    np.random.seed(10101)
    np.random.shuffle(annotation_lines)
    np.random.seed(None)
    num_val = int(len(annotation_lines) * val_split)
    num_train = len(annotation_lines) - num_val

    batch_size = 32
    input_shape = (416, 416)

    num = len(annotation_lines)
    if num == 0 or batch_size <= 0:
        raise ValueError

    lines = tf.convert_to_tensor(annotation_lines[:10], tf.string)
    """ start parser """
    image_data = []
    box_data = []
    for line in lines:
        image, box = get_random_data(line.numpy().decode(), input_shape, random=True)
        image_data.append(image)
        box_data.append(box)

    image_data = np.array(image_data)
    box_data = np.array(box_data)

    y_true = [tf.convert_to_tensor(y, tf.float32) for y in preprocess_true_boxes(box_data, input_shape, anchors, num_classes)]
    image_data = tf.convert_to_tensor(image_data, tf.float32)
    return (image_data, *y_true)


def test_zip_dataset():
    """ 尝试zip dataset，但还是失败了 """
    annotation_path = 'train.txt'
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)

    val_split = 0.1
    with open(annotation_path) as f:
        annotation_lines = f.readlines()
    np.random.seed(10101)
    np.random.shuffle(annotation_lines)
    np.random.seed(None)
    num_val = int(len(annotation_lines) * val_split)
    num_train = len(annotation_lines) - num_val

    batch_size = 32
    input_shape = (416, 416)

    num = len(annotation_lines)
    if num == 0 or batch_size <= 0:
        raise ValueError

    def parser(lines):
        image_data = []
        box_data = []
        for line in lines:
            image, box = get_random_data(line.numpy().decode(), input_shape, random=True)
            image_data.append(image)
            box_data.append(box)

        image_data = np.array(image_data)
        box_data = np.array(box_data)

        y_true = [tf.convert_to_tensor(y, tf.float32) for y in preprocess_true_boxes(box_data, input_shape, anchors, num_classes)]
        image_data = tf.convert_to_tensor(image_data, tf.float32)
        return (image_data, *y_true)

    x_set = (tf.data.Dataset.from_tensor_slices(annotation_lines).
             apply(tf.data.experimental.shuffle_and_repeat(batch_size * 300, seed=66)).
             batch(batch_size, drop_remainder=True).
             map(lambda lines: py_function(parser, [lines], [tf.float32] * (1 + len(anchors) // 3))))
    y_set = tf.data.Dataset.from_tensors(tf.zeros(batch_size, tf.float32)).repeat()
    dataset = tf.data.Dataset.zip((x_set, y_set))

    sample = next(iter(dataset))


# NOTE 使用了Sequence但是数据加载速度还是不行
#  class YOLOSequence(Sequence):
#     def __init__(self, annotation_lines, batch_size, input_shape, anchors, num_classes):
#         self.num = len(annotation_lines)
#         self.annotation_lines = annotation_lines
#         self.batch_size = batch_size
#         self.input_shape = input_shape
#         self.anchors = anchors
#         self.num_classes = num_classes
#         if self.num == 0 or self.batch_size <= 0:
#             raise ValueError

#     def __len__(self):
#         return self.num // self.batch_size

#     def __getitem__(self, idx):
#         image_data = []
#         box_data = []
#         for b in range(self.batch_size):
#             image, box = get_random_data(self.annotation_lines[idx * self.batch_size + b],
#                                          self.input_shape, random=True)
#             image_data.append(image)
#             box_data.append(box)
#         image_data = np.array(image_data)
#         box_data = np.array(box_data)
#         y_true = preprocess_true_boxes(box_data, self.input_shape, self.anchors, self.num_classes)
#         return [image_data, *y_true], np.zeros(self.batch_size)
#     def on_epoch_end(self):
#         np.random.shuffle(self.annotation_lines)


def test_dataset():
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/tiny_yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)
    input_shape = (416, 416)  # multiple of 32, hw
    batch_size = 1
    annotation_path = 'train.txt'
    with open(annotation_path) as f:
        lines = f.readlines()

    tset = create_dataset(lines[:2000], batch_size, input_shape, anchors, num_classes, False)
    ter = iter(tset)

    for i in range(3):
        a, b = next(ter)
        img, lb1, lb2 = a[0][0], a[1][0], a[2][0]
        plt.imshow(img.numpy())
        plt.show()

    true_confidence = lb1[..., 4:5]

    obj_mask = true_confidence[..., 0] > .7

    tf.boolean_mask(lb1, obj_mask)

    # NOTE 他就是按比例缩小图像的。
    np.min(a[0][0])
    np.max(a[0][0])


def center_to_corner(true_box: np.ndarray) -> np.ndarray:
    x1 = (true_box[:, 0:1] - true_box[:, 2:3] / 2)
    y1 = (true_box[:, 1:2] - true_box[:, 3:4] / 2)
    x2 = (true_box[:, 0:1] + true_box[:, 2:3] / 2)
    y2 = (true_box[:, 1:2] + true_box[:, 3:4] / 2)
    xyxy_box = np.hstack([x1, y1, x2, y2])
    return xyxy_box


def test_get_random_data():
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/tiny_yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)
    input_shape = (416, 416)  # multiple of 32, hw
    batch_size = 1
    annotation_path = 'train.txt'
    with open(annotation_path) as f:
        lines = f.readlines()

    for i in range(10):
        img, box = get_random_data(lines[i], input_shape, False)
        box = box[np.newaxis, :2, :]
        # print(box,input_shape,anchors,num_classes)
        y_true = preprocess_true_boxes(box, input_shape, anchors, num_classes, is_print=True)

        for a in y_true:
            true_box = a[np.where(a[..., 4] > 0)]
            true_box[:, :2] *= input_shape[::-1]
            true_box[:, 2:4] *= input_shape[::-1]

            xyxy_box = center_to_corner(true_box)
            # print(xyxy_box)
            for b in xyxy_box:
                cv2.rectangle(img, tuple(b[:2].astype(int)), tuple(b[2:4].astype(int)), (255, 0, 0))

        # plt.imshow(img)
        # plt.imsave('/home/zqh/Documents/K210-yolo-v3/tmp/house.jpg', img)
        # !  经过测试 y true 的xywh最终绝对是对应全局的【0-1】
        # ! 但是为什么在yolo loss里又好像是gird scale？
        # ! 他这里给y true的的确是全局的[0-1],但是在yolo loss的时候他才转换到grid尺度.
        
test_get_random_data()

def test_resize_img():
    classes_path = 'model_data/voc_classes.txt'
    anchors_path = 'model_data/tiny_yolo_anchors.txt'
    class_names = get_classes(classes_path)
    num_classes = len(class_names)
    anchors = get_anchors(anchors_path)
    input_shape = (224, 320)  # multiple of 32, hw
    batch_size = 1
    annotation_path = 'train.txt'
    with open(annotation_path) as f:
        lines = f.readlines()

    img, box = get_random_data(lines[3], input_shape, False)
    plt.imshow(img)
    plt.imsave('')


def test_mobile_yolo_05():
    model = keras.applications.MobileNet(input_shape=(224, 320, 3),
                                         alpha=.5,
                                         include_top=False,
                                         weights='imagenet')
    model.summary()


def test_mobile_yolo_75():
    from keras_applications.mobilenet import MobileNet
    m = MobileNet((224, 320, 3), .75, include_top=False)  # type:keras.Model


def make_modelnet_base_weights():
    inputs = keras.Input((224, 320, 3))

    from tensorflow.python.keras.applications import MobileNet as o_moblie
    for alpha in [.5, .75, 1.]:
        om = o_moblie(input_tensor=inputs, alpha=alpha, include_top=False)  # type:keras.Model
        oweights = om.get_weights()
        nm = MobileNet(input_tensor=inputs, alpha=alpha)
        nweights = nm.get_weights()

        for i in range(len(nweights)):
            nweights[i] = oweights[i][[slice(0, s) for s in nweights[i].shape]]

        nm.set_weights(nweights)

        keras.models.save_model(nm, f'model_data/mobilenet_v1_base_{int(alpha*10)}.h5')


def test_load_old_model():
    m = keras.models.load_model('model_data/yolo_model_body_1_new.h5')  # type:keras.Model
    m.summary()

    model = mobile_yolo_body(keras.Input((224, 320, 3)), 3, 20, 1.)
    model.summary()
    keras.models.save_model(model, 'test_logs/small_mobilenet.h5')
    new_weights = model.get_weights()
    old_weights = m.get_weights()

    for i in range(len(new_weights)):
        new_weights[i] = old_weights[i][[slice(0, s) for s in new_weights[i].shape]]

    model.set_weights(new_weights)

    keras.models.save_model(model, 'test_logs/small_mobilenet.h5')


def test_new_model():
    model = mobile_yolo_body(keras.Input((224, 320, 3)), 3, 20, .75)
    model.summary()


# from tensorflow.python.keras.applications import MobileNetV2
# md = MobileNetV2((224, 320, 3), alpha=.75, include_top=False, weights=None)
# md.summary()
