
import time
import keras
import numpy as np
from src.loading_data.get_data import get_fold_is, load_cv_data, load_train_test_data, make_importance_sampling_dataset, normalize_1d_features, normalize_1d_features_with_mean_std, save_cv_data, stack_1d_features, get_tf_data
from src.cnn_emos.nn_model import NNModel
from src.cnn_emos.nn_forecast import CNNEMOS
import tensorflow as tf
import pickle
import os
import random

from src.visualization.pit import comp_pit_score_tf

features_names = ['wind_speed', 'press', 'kinetic', 'humid', 'geopot']

features_names_dict = {name: 1 for name in features_names}

features_names_dict['wind_speed'] = 15

ignore = ['229', '285', '323']

bounds = {7.5: 1, 9: 3, 12: 4, 15: 9, 100: 15}

# seed = 100

# tf.random.set_seed(seed)
# np.random.seed(seed)
# random.seed(seed)

batch_size = 64

# train_data = make_importance_sampling_dataset(train_data, bounds)

# train_data = train_data.cache()

# dataset_length = [i for i,_ in enumerate(train_data)][-1] + 1

# print(dataset_length)

# # dataset_length = 28595

train_data3, test_data3, data_info = load_cv_data(3, features_names_dict)

steps3 = train_data3.cardinality() // batch_size

train_data3 = train_data3.shuffle(train_data3.cardinality().numpy())

train_data3 = train_data3.batch(batch_size)

train_data3 = train_data3.prefetch(tf.data.experimental.AUTOTUNE)

train_data3 = train_data3.repeat()

test_data3 = test_data3.batch(len(test_data3))

test_data3 = test_data3.prefetch(tf.data.experimental.AUTOTUNE)


train_data2, test_data2, data_info = load_cv_data(2, features_names_dict)

steps2 = train_data2.cardinality() // batch_size

train_data2 = train_data2.shuffle(train_data2.cardinality().numpy())

train_data2 = train_data2.batch(batch_size)

train_data2 = train_data2.prefetch(tf.data.experimental.AUTOTUNE)

train_data2 = train_data2.repeat()

test_data2 = test_data2.batch(len(test_data2))

test_data2 = test_data2.prefetch(tf.data.experimental.AUTOTUNE)



train_data1, test_data1, data_info = load_cv_data(1, features_names_dict)

steps1 = train_data1.cardinality() // batch_size

train_data1 = train_data1.shuffle(train_data1.cardinality().numpy())

train_data1 = train_data1.batch(batch_size)

train_data1 = train_data1.prefetch(tf.data.experimental.AUTOTUNE)

train_data1 = train_data1.repeat()

test_data1 = test_data1.batch(len(test_data1))

test_data1 = test_data1.prefetch(tf.data.experimental.AUTOTUNE)




forecast_distribution = 'distr_mixture'
distribution_1 = 'distr_trunc_normal'
distribution_2 = 'distr_log_normal'

loss_function = 'loss_twCRPS_sample'
chain_function = 'chain_function_normal_cdf_plus_constant'
chain_function_mean = 9
chain_function_std = 1
chain_function_constant = 0.015

optimizer = 'adam'
learning_rate = 0.000105

dense_l1_regularization = 0.000
dense_l2_regularization = 0.031658
hidden_units_list = [170, 170]
conv_7x7_units = 4
conv_5x5_units = 4
conv_3x3_units = 4

metrics = ['twCRPS_12']# ['twCRPS_10', 'twCRPS_12', 'twCRPS_15']
metrics = None
saving = False

epochs = 130

filepath = '/net/pc200239/nobackup/users/hakvoort/models/conv_nn/'

if loss_function == 'loss_twCRPS_sample':
    name = 'twCRPS'
    name += '_mean_' + str(chain_function_mean)
    name += '_std_' + str(chain_function_std)
    name += '_constant_' + str(chain_function_constant)
elif loss_function == 'loss_CRPS_sample':
    name = 'CRPS'

filepath += name + '_'

if forecast_distribution == 'distr_mixture':
    filepath += 'mixture_'
elif forecast_distribution == 'distr_trunc_normal':
    filepath += 'trunc_normal_'
elif forecast_distribution == 'distr_log_normal':
    filepath += 'log_normal_'

filepath += 'epochs_' + str(epochs) 



filepath += 'run_115_fold_3_intermediate_v2'

print(filepath)

# make a folder
if saving:
    os.makedirs(filepath, exist_ok=True)

setup_distribution = {
    'forecast_distribution': forecast_distribution,
    'distribution_1': distribution_1,
    'distribution_2': distribution_2,
}

setup_nn_architecture = {
    'hidden_units_list': hidden_units_list,
    'dense_l1_regularization': dense_l1_regularization,
    'dense_l2_regularization': dense_l2_regularization,

    'conv_7x7_units': conv_7x7_units,
    'conv_5x5_units': conv_5x5_units,
    'conv_3x3_units': conv_3x3_units,
}

setup_loss = {
    'loss_function': loss_function,
    'chain_function': chain_function,
    'chain_function_mean': chain_function_mean,
    'chain_function_std': chain_function_std,
    'chain_function_constant': chain_function_constant,
}

setup_optimizer = {
    'optimizer': optimizer,
    'learning_rate': learning_rate,
}

setup = {
    'setup_distribution': setup_distribution,
    'features_names': features_names,
    'setup_loss': setup_loss,
    'setup_optimizer': setup_optimizer,
    'sample_size': 1000,
    'setup_nn_architecture': setup_nn_architecture,

    'features_1d_mean': data_info['features_1d_mean'],
    'features_1d_std': data_info['features_1d_std'],
    'metrics': metrics,
}

if saving:
    with open(filepath + '/attributes', 'wb') as f:
        pickle.dump(setup, f)


my_list = []

filepath = '/net/pc200239/nobackup/users/hakvoort/models/conv_nn/'

with open(filepath + 'epochs_115_twcrps_m9_std1_c_015.pickle', 'rb') as f:
    my_list = pickle.load(f)

print(my_list)

print(np.mean(my_list))
print(np.var(my_list))

train_data_list = [train_data1, train_data2, train_data3]
test_data_list = [test_data1, test_data2, test_data3]
steps_list = [steps1, steps2, steps3]


for _ in range(0, 100):
    best_epochs = []
    for x in [0,1,2]:
        train_data = train_data_list[x]
        test_data = test_data_list[x]
        steps_per_epoch = steps_list[x]

        nn = CNNEMOS(**setup)

        #start the time
        time_start = time.time()

        early_stopping = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

        history = nn.fit(train_data, epochs=epochs, validation_data=test_data , early_stopping=early_stopping, steps_per_epoch=steps_per_epoch, verbose=0)

        best_epoch = early_stopping.stopped_epoch - early_stopping.patience

        if best_epoch < 0:
            best_epoch = epochs

        print(f'Best epoch: {best_epoch}')

        best_epochs.append(best_epoch)

    my_list.append(best_epochs)

    filepath = '/net/pc200239/nobackup/users/hakvoort/models/conv_nn/'

    with open(filepath + 'epochs_115_twcrps_m9_std1_c_015.pickle', 'wb') as f:
        pickle.dump(my_list, f)

    print(my_list)


# if saving:
#     nn.save_weights(filepath)
#     print("Model saved")

# #end the time
# time_end = time.time()

# print("Time: ", time_end - time_start)

# print(nn.CRPS(test_data, 10000))

# print(nn.twCRPS(test_data, [12], 10000)[0])

# values = np.linspace(0, 20, 40)

# brierscores = nn.Brier_Score(test_data, values)

# # save the history
# if saving:
#     with open(filepath + '/history.pickle', 'wb') as f:
#         pickle.dump(history.history, f)
#         print("History saved")





