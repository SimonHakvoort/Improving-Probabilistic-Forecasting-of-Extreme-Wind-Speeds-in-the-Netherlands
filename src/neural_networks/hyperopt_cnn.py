import string
from typing import Tuple
import numpy as np
import optuna
import tensorflow as tf

from src.neural_networks.get_data import load_cv_data
from src.neural_networks.nn_forecast import NNForecast

class ObjectiveCNN:
    def __init__(self, feature_names_dict, objectives, train_amount = 3):
        self.feature_names_dict = feature_names_dict
        self.objectives = objectives
        self.train_amount = train_amount
        self.feature_names_list = list(feature_names_dict.keys())

        # check if objectives is correct
        for objective in objectives:
            if objective != 'CRPS' and objective[:6] != 'twCRPS':
                raise ValueError('The objective is not valid. Please use either CRPS or twCRPS')


    def get_data_i(self, i: int, batch_size: int) -> Tuple[tf.data.Dataset, tf.data.Dataset]:
        """
        Preprocess the data for the specific fold.

        Arguments:
            i (int): fold number
            batch_size (int): batch size for the training data.

        Returns:
            Tuple[tf.data.Dataset, tf.data.Dataset] containing the training data (0) and the test data (1)
        """
        train_data, test_data, data_info = load_cv_data(i, self.feature_names_dict)

        train_data = train_data.shuffle(len(train_data))

        train_data = train_data.batch(batch_size)

        test_data = test_data.batch(len(test_data))

        test_data = test_data.prefetch(tf.data.experimental.AUTOTUNE)

        return train_data, test_data

    def compute_objective(self, nnforecast: NNForecast, objective: string, test_data: tf.data.Dataset) -> float:
        """
        Computes the objective values.

        Arguments:
            nnforecast (NNForecast): a NNForecast object.
            objective (string): a string specifying the objective.
            test_data (tf.data.Dataset): the test data.

        Returns:
            the objective value (float).
        """
        if objective == 'CRPS':
            return nnforecast.CRPS(test_data, 50000)
        # check if the first 6 characters are 'twCRPS'
        elif objective[:6] == 'twCRPS':
            # get the numbers after 'twCRPS'
            twCRPS_num = objective[6:]
            return nnforecast.twCRPS(test_data, [int(twCRPS_num)], 50000)[0]
        else:
            raise ValueError("Incorrect objective, please use CRPS or twCRPS")
        

    def train_on_fold_i(self, setup: dict, fold: int, epochs: int, batch_size: int) -> Tuple[np.ndarray, int]:
        """
        Trains a single model with a specific setup on a specific fold.

        Arguments:
            setup (dict): the setup of the NNForecast.
            fold (int): the fold on which we model is trained.
            epochs (int): the number of epochs.
            batch_size (int): the batch size.

        Returns:
            the objective values and the best epoch.
        """
        train_data, test_data = self.get_data_i(fold, batch_size)

        train_data = train_data.prefetch(tf.data.experimental.AUTOTUNE)

        nn_forecast = NNForecast(**setup)

        early_stopping = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)

        nn_forecast.fit(train_data, epochs, test_data, early_stopping=early_stopping)

        objective_values = np.zeros(len(self.objectives))
        for i, objective in enumerate(self.objectives):
            objective_values[i] = self.compute_objective(nn_forecast, objective, test_data)


        best_epoch = early_stopping.stopped_epoch - early_stopping.patience

        return objective_values, best_epoch
    
    def __call__(self, trial: optuna.Trial) -> Tuple[float, float]:
        setup = {}

        forecast_distribution = trial.suggest_categorical('Forecast Distribution', ['distr_trunc_normal', 'distr_log_normal', 'distr_mixture'])

        distribution_1 = 'distr_trunc_normal'
        distribution_2 = 'distr_log_normal'

        loss_function = 'loss_twCRPS_sample'

        chain_function = 'chain_function_normal_cdf_plus_constant'

        chain_function_mean = trial.suggest_float('cf mean', -5, 15)
        chain_function_std = trial.suggest_float('cf std', 0.0001, 10, log=True)
        chain_function_constant = trial.suggest_float('cf constant', 0.000001, 1, log=False)

        optimizer = trial.suggest_categorical('Optimizer', ['adam', 'sgd'])
        learning_rate = trial.suggest_float('Learning Rate', 0.0001, 0.1)

        dense_l2_regularization = trial.suggest_float('L2 Regularization', 0.00005, 0.1)

        number_of_layers = trial.suggest_int('Number of Layers', 1, 5)
        number_of_units = trial.suggest_int('Number of Units per Layer', 30, 200, step=10)

        hidden_units_list = [number_of_units for _ in range(number_of_layers)]

        batch_size = trial.suggest_categorical('Batch Size', [16, 32, 64, 128, 256, 512, 1024])

        conv_7x7_units = 4
        conv_5x5_units = 4
        conv_3x3_units = 4

        sample_size = 1000
        epochs = 200

        setup_distribution = {
            'forecast_distribution': forecast_distribution,
            'distribution_1': distribution_1,
            'distribution_2': distribution_2,
        }

        setup_nn_architecture = {
            'hidden_units_list': hidden_units_list,
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
            'features_names': self.feature_names_list,
            'setup_loss': setup_loss,
            'setup_optimizer': setup_optimizer,
            'sample_size': sample_size,
            'setup_nn_architecture': setup_nn_architecture,
        }

        folds = [1,2,3]
        objective_values = np.zeros(len(self.objectives))

        num_epochs = []

        for fold in folds:
            losses = np.zeros(len(self.objectives))
            for _ in range(self.train_amount):
                losses, best_epoch = self.train_on_fold_i(setup, fold, epochs, batch_size)

                objective_values += losses
                num_epochs.append(best_epoch)

        losses /= (3 * self.train_amount)
        
        avg_epochs = np.mean(num_epochs)

        trial.set_user_attr('Average Epochs', avg_epochs)

        return objective_values.tolist()




