

def benchmark_nested_break():
    """
    There are several ways to do a nested break, but which one is best?
    """
    import ubelt as ub
    import pandas as pd
    import timerit
    import itertools as it

    def method1_itertools(n1, n2):
        for i, j in it.product(range(n1), range(n2)):
            if i == 2 and j == 2:
                break

    def method2_except(n1, n2):
        class Found(Exception):
            pass
        try:
            for i in range(n1):
                for j in range(n2):
                    if i == 2 and j == 2:
                        raise Found
        except Found:
            pass

    def method3_gendef(n1, n2):
        def gen():
            for i in range(n1):
                for j in range(n2):
                    yield i, j

        for i, j in gen():
            if i == 2 and j == 2:
                break

    def method4_genexp(n1, n2):
        genexpr = ((i, j) for i in range(n1) for j in range(n2))
        for i, j in genexpr:
            if i == 2 and j == 2:
                break

    method_lut = locals()  # can populate this some other way

    # Change params here to modify number of trials
    ti = timerit.Timerit(100000, bestof=100, verbose=1)

    # if True, record every trail run and show variance in seaborn
    # if False, use the standard timerit min/mean measures
    RECORD_ALL = True

    # These are the parameters that we benchmark over
    basis = {
        'method': ['method1_itertools', 'method2_except', 'method3_gendef', 'method4_genexp'],
        'n1': list(range(10)),
        'n2': list(range(10)),
        # 'param_name': [param values],
    }
    xlabel = 'size'
    xinput_labels = ['n1', 'n2']

    # Set these to param labels that directly transfer to method kwargs
    kw_labels = ['n1', 'n2']
    # Set these to empty lists if they are not used
    group_labels = {
        'style': [],
        'size': [],
    }
    group_labels['hue'] = list(
        (ub.oset(basis) - {xlabel} - xinput_labels) - set.union(*map(set, group_labels.values())))
    grid_iter = list(ub.named_product(basis))

    # For each variation of your experiment, create a row.
    rows = []
    for params in grid_iter:
        size = params['n1'] * params['n2']
        params['size'] = size
        group_keys = {}
        for gname, labels in group_labels.items():
            group_keys[gname + '_key'] = ub.repr2(
                ub.dict_isect(params, labels), compact=1, si=1)
        key = ub.repr2(params, compact=1, si=1)
        # Make any modifications you need to compute input kwargs for each
        # method here.
        kwargs = ub.dict_isect(params.copy(),  kw_labels)

        method = method_lut[params['method']]
        # Timerit will run some user-specified number of loops.
        # and compute time stats with similar methodology to timeit
        for timer in ti.reset(key):
            # Put any setup logic you dont want to time here.
            # ...
            with timer:
                # Put the logic you want to time here
                method(**kwargs)

        if RECORD_ALL:
            # Seaborn will show the variance if this is enabled, otherwise
            # use the robust timerit mean / min times
            # chunk_iter = ub.chunks(ti.times, ti.bestof)
            # times = list(map(min, chunk_iter))  # TODO: timerit method for this
            times = ti.robust_times()
            for time in times:
                row = {
                    # 'mean': ti.mean(),
                    'time': time,
                    'key': key,
                    **group_keys,
                    **params,
                }
                rows.append(row)
        else:
            row = {
                'mean': ti.mean(),
                'min': ti.min(),
                'key': key,
                **group_keys,
                **params,
            }
            rows.append(row)

    time_key = 'time' if RECORD_ALL else 'min'

    # The rows define a long-form pandas data array.
    # Data in long-form makes it very easy to use seaborn.
    data = pd.DataFrame(rows)
    data = data.sort_values(time_key)

    if RECORD_ALL:
        # Show the min / mean if we record all
        min_times = data.groupby('key').min().rename({'time': 'min'}, axis=1)
        mean_times = data.groupby('key')[['time']].mean().rename({'time': 'mean'}, axis=1)
        stats_data = pd.concat([min_times, mean_times], axis=1)
        stats_data = stats_data.sort_values('min')
    else:
        stats_data = data

    USE_OPENSKILL = 1
    if USE_OPENSKILL:
        # Lets try a real ranking method
        # https://github.com/OpenDebates/openskill.py
        import openskill
        method_ratings = {m: openskill.Rating() for m in basis['method']}

    other_keys = sorted(set(stats_data.columns) - {'key', 'method', 'min', 'mean', 'hue_key', 'size_key', 'style_key'})
    for params, variants in stats_data.groupby(other_keys):
        variants = variants.sort_values('mean')
        ranking = variants['method'].reset_index(drop=True)

        mean_speedup = variants['mean'].max() / variants['mean']
        stats_data.loc[mean_speedup.index, 'mean_speedup'] = mean_speedup
        min_speedup = variants['min'].max() / variants['min']
        stats_data.loc[min_speedup.index, 'min_speedup'] = min_speedup

        if USE_OPENSKILL:
            # The idea is that each setting of parameters is a game, and each
            # "method" is a player. We rank the players by which is fastest,
            # and update their ranking according to the Weng-Lin Bayes ranking
            # model. This does not take the fact that some "games" (i.e.
            # parameter settings) are more important than others, but it should
            # be fairly robust on average.
            old_ratings = [[r] for r in ub.take(method_ratings, ranking)]
            new_values = openskill.rate(old_ratings)  # Not inplace
            new_ratings = [openskill.Rating(*new[0]) for new in new_values]
            method_ratings.update(ub.dzip(ranking, new_ratings))

    print('Statistics:')
    print(stats_data)

    if USE_OPENSKILL:
        from openskill import predict_win
        win_prob = predict_win([[r] for r in method_ratings.values()])
        skill_agg = pd.Series(ub.dzip(method_ratings.keys(), win_prob)).sort_values(ascending=False)
        print('method_ratings = {}'.format(ub.repr2(method_ratings, nl=1)))
        print('Aggregated Rankings =\n{}'.format(skill_agg))

    plot = True
    if plot:
        # import seaborn as sns
        # kwplot autosns works well for IPython and script execution.
        # not sure about notebooks.
        import kwplot
        sns = kwplot.autosns()
        plt = kwplot.autoplt()

        plotkw = {}
        for gname, labels in group_labels.items():
            if labels:
                plotkw[gname] = gname + '_key'

        # Your variables may change
        ax = kwplot.figure(fnum=1, doclf=True).gca()
        sns.lineplot(data=data, x=xlabel, y=time_key, marker='o', ax=ax, **plotkw)
        ax.set_title(f'Benchmark Nested Breaks: #Trials {ti.num}, bestof {ti.bestof}')
        ax.set_xlabel(f'{xlabel}')
        ax.set_ylabel('Time')
        # ax.set_xscale('log')
        ax.set_yscale('log')

        try:
            __IPYTHON__
        except NameError:
            plt.show()


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/timerit/examples/benchmark_nested_break.py
    """
    benchmark_nested_break()
