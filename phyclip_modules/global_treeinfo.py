from __future__ import division
import ete3
import re
import itertools
import math
import numpy as np

# nCr
def nCr(N, R):
    try:
        return math.factorial(N) / (math.factorial(R) * math.factorial(N - R))
    except:
        return 0

class get_global_tree_info(object):
    '''
    Get global tree information
    '''
    def __init__(self, tree_object=None, leaf_dist_to_node=None, leafpair_to_distance=None, nodepair_to_pval=None, treeinfo_fname=None):
        self.tree_object = tree_object
        self.leaf_dist_to_node = leaf_dist_to_node
        self.leafpair_to_distance = leafpair_to_distance
        self.nodepair_to_pval = nodepair_to_pval
        self.treeinfo_fname = treeinfo_fname

        if len(self.leaf_dist_to_node) == 0 and len(self.leafpair_to_distance) == 0 and len(self.nodepair_to_pval) == 0:
            self.initial_write_state = 'w'
        else:
            self.initial_write_state = 'a'

    def node_indexing(self):
        '''
        1) Index tree nodes by level-order.
        2) Annotate node id to tree string.
        3) Get leaf to node distances.
        4) Calculate pairwise inter-node distances using leaf to node distances
        '''

        tree_string = self.tree_object.write(format=5)  # append node id annotation
        taxon_list = self.tree_object.get_leaf_names()

        node_to_leaves = {}
        nindex_to_node = {}
        node_to_nindex = {}

        # level-order traversal
        for n, node in enumerate(self.tree_object.traverse()):
            if node.is_leaf():
                continue

            node_to_leaves[n] = node.get_leaf_names()
            nindex_to_node[n] = node
            node_to_nindex[node] = n

            # node annotation for final tree output
            node_string = re.sub('[^\)]+$', '', node.write(format=5))
            tree_string = tree_string.replace(node_string, '{}[&NODE_ID={}]'.format(node_string, n))

            # distance of leaf to each of its ancestral node
            for leaf_node in node.get_leaves():
                leaf = leaf_node.name
                try:
                    # continue if we have already recorded the distance for leaf-node.
                    dist = self.leaf_dist_to_node[leaf][n]
                    continue
                except:
                    dist = leaf_node.get_distance(node)

                try:
                    self.leaf_dist_to_node[leaf][n] = dist
                except:
                    self.leaf_dist_to_node[leaf] = {n: dist}

                with open(self.treeinfo_fname, self.initial_write_state) as output:
                    output.write('L{},N{},D{}\n'.format(leaf, n, dist))

        # Calulating inter-node distances
        ancestral_nodepair_to_dist = {}
        for leaf, node_to_dist in self.leaf_dist_to_node.items():
            ancestors_of_leaf = node_to_dist.keys()[:]
            for (i,j) in itertools.combinations(ancestors_of_leaf, 2):

                if (i in ancestral_nodepair_to_dist and j in ancestral_nodepair_to_dist[i]) or (j in ancestral_nodepair_to_dist and i in ancestral_nodepair_to_dist[j]):
                    continue
                else:
                    ij_dist = abs(node_to_dist[i] - node_to_dist[j])

                    try:
                        ancestral_nodepair_to_dist[i][j] = ij_dist
                    except:
                        ancestral_nodepair_to_dist[i] = {j:ij_dist}

                    try:
                        ancestral_nodepair_to_dist[j][i] = ij_dist
                    except:
                        ancestral_nodepair_to_dist[j] = {i:ij_dist}

        sibling_nodepair_to_dist = {}
        for (i,j) in itertools.combinations(ancestral_nodepair_to_dist.keys()[:], 2):
            if (i in ancestral_nodepair_to_dist and j in ancestral_nodepair_to_dist[i]) or (i in sibling_nodepair_to_dist and j in sibling_nodepair_to_dist[i]) or (j in sibling_nodepair_to_dist and i in sibling_nodepair_to_dist[j]):
                continue
            else:
                ancestors_to_i = [node for node in ancestral_nodepair_to_dist[i].keys() if node < i]
                ancestors_to_j = [node for node in ancestral_nodepair_to_dist[j].keys() if node < j]
                common_ancestors = sorted(set(ancestors_to_i)&set(ancestors_to_j))
                common_ancestor = common_ancestors[-1]
                ij_dist = ancestral_nodepair_to_dist[i][common_ancestor] + ancestral_nodepair_to_dist[j][common_ancestor]

                try:
                    sibling_nodepair_to_dist[i][j] = ij_dist
                except:
                    sibling_nodepair_to_dist[i] = {j:ij_dist}

                try:
                    sibling_nodepair_to_dist[j][i] = ij_dist
                except:
                    sibling_nodepair_to_dist[j] = {i:ij_dist}

        nodepair_to_dist = ancestral_nodepair_to_dist.copy()
        for i in nodepair_to_dist.keys():
            try:
                nodepair_to_dist[i].update(sibling_nodepair_to_dist[i])
            except:
                continue

        return tree_string, taxon_list, node_to_leaves, nindex_to_node, node_to_nindex, self.leaf_dist_to_node, nodepair_to_dist

    def pwdist_dist_and_ancestral_trace(self, all_taxa_len, node_to_leaves, nindex_to_node, node_to_nindex):
        '''
        1) Get pairwise distances of all leaves
        2) Get ancestral/descendant traces
        3) Get pairwise distance distributions of nodes
        '''
        if len(self.leafpair_to_distance) < nCr(all_taxa_len, 2):
            print ('Get pairwise distances between leaves...')
            for x, y in itertools.combinations(self.tree_object.get_leaves(), 2):
                leaf_x = x.name
                leaf_y = y.name
                try:
                    # continue if distance between leaves has already been recorded
                    dist = self.leafpair_to_distance[(leaf_x, leaf_y)]
                    dist = self.leafpair_to_distance[(leaf_y, leaf_x)]
                    continue
                except:
                    dist = x.get_distance(y)

                self.leafpair_to_distance[(leaf_x, leaf_y)] = self.leafpair_to_distance[(leaf_y, leaf_x)] = dist
                with open(self.treeinfo_fname, 'a') as output:
                    output.write('I{},J{},D{}\n'.format(leaf_x, leaf_y, dist))

        node_to_ancestral_nodes = {}
        node_to_descendant_nodes = {}
        node_to_pwdist = {}
        node_to_mean_pwdist = {}

        for n, leaves in node_to_leaves.items():
            ancestors_to_n = [node_to_nindex[anc] for anc in nindex_to_node[n].iter_ancestors()]
            node_to_ancestral_nodes[n] = ancestors_to_n
            for anc in ancestors_to_n:
                try:
                    node_to_descendant_nodes[anc].append(n)
                except:
                    node_to_descendant_nodes[anc] = [n]

            pwdist = sorted([self.leafpair_to_distance[(x,y)] for (x,y) in itertools.combinations(leaves, 2)])
            node_to_pwdist[n] = pwdist
            node_to_mean_pwdist[n] = np.mean(pwdist)

        return self.leafpair_to_distance, node_to_pwdist, node_to_mean_pwdist, node_to_ancestral_nodes, node_to_descendant_nodes

    def get_global_pval(self, no_of_internal_nodes, hytest_method, node_to_leaves, node_to_ancestral_nodes, node_to_pwdist, leafpair_to_distance):
        '''
        Perform all inter-clusters' hypotheses tests
        '''
        if len(self.nodepair_to_pval) < nCr(no_of_internal_nodes, 2):
            from phyclip_modules import inter_cluster_hytest

            print ('Performing global {} tests...'.format(hytest_method))

            for i,j in itertools.combinations(node_to_leaves.keys(), 2):
                try:
                    pval = self.nodepair_to_pval[(i,j)]
                    continue
                except:
                    try:
                        pval = self.nodepair_to_pval[(j,i)]
                        continue
                    except:
                        if (j in node_to_ancestral_nodes and i in node_to_ancestral_nodes[j]) or (i in node_to_ancestral_nodes and j in node_to_ancestral_nodes[i]):
                            pval = inter_cluster_hytest(node_to_pwdist[i], node_to_pwdist[j]).hytest(hytest_method)
                        else:
                            ij_pwdist = sorted([leafpair_to_distance[(x,y)] for x,y in itertools.combinations(list(set(node_to_leaves[i])|set(node_to_leaves[j])), 2)])
                            # take the conservative (max) p-value comparing node i/j individually to i+j
                            pval = max([inter_cluster_hytest(node_to_pwdist[i], ij_pwdist).hytest(hytest_method), inter_cluster_hytest(node_to_pwdist[j], ij_pwdist).hytest(hytest_method)])

                        self.nodepair_to_pval[(i,j)] = pval

                        with open(self.treeinfo_fname, 'a') as output:
                            output.write('I{},J{},{}{}\n'.format(i, j, 'KP' if hytest_method == 'Kuiper' else 'KS', pval))

        return self.nodepair_to_pval